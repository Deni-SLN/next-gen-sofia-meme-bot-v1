"""Risk gate (FR-TB-004) — final safety checkpoint before any order intent.

Fail-closed: NaN, Infinity, missing mandatory metric, or stale data always
rejects. There is no AI override for hard-reject.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_RISK_CONFIG: dict = {
    "risk_version": "risk-gate-v1",
    "max_position_allocation_usd": 200.0,
    "max_total_exposure_usd": 1000.0,
    "daily_loss_limit_usd": 150.0,
    "max_drawdown_pct": 20.0,
    "max_concurrent_positions": 5,
    "cooldown_after_loss_seconds": 300,
    "max_slippage_pct": 2.0,
    "min_liquidity_usd": 10000.0,
    "max_fee_pct": 1.0,
    "max_price_impact_pct": 3.0,
    "max_signal_age_seconds": 300,
    "min_risk_reward": 1.5,
    "max_position_pct_of_equity": 10.0,
}


@dataclass
class RiskGateInput:
    mode: str
    bot_running: bool
    kill_switch_active: bool
    equity_usd: float
    open_positions_count: int
    open_exposure_usd: float
    daily_realized_pnl_usd: float
    peak_equity_usd: float
    last_loss_at: datetime | None
    now: datetime
    signal_created_at: datetime
    signal_expires_at: datetime | None
    reference_price: float | None
    liquidity_usd: float | None
    slippage_pct: float | None
    fee_pct: float | None
    price_impact_pct: float | None
    risk_reward: float | None
    hard_reject: bool
    market_data_age_seconds: float | None
    # False when any open position lacks a usable mark, which makes equity and
    # drawdown unknown. Defaults True so callers that hold no open positions
    # (and existing tests) keep their prior behaviour.
    valuation_complete: bool = True


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    sized_allocation_usd: float | None = None


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def evaluate_risk_gate(data: RiskGateInput, config: dict | None = None) -> RiskDecision:
    cfg = {**DEFAULT_RISK_CONFIG, **(config or {})}
    reasons: list[str] = []
    checks: dict = {}

    checks["kill_switch"] = not data.kill_switch_active
    if data.kill_switch_active:
        reasons.append("emergency kill switch active")
    checks["bot_running"] = data.bot_running
    if not data.bot_running:
        reasons.append("bot is not running")
    checks["valid_mode"] = data.mode == "PAPER"
    if not checks["valid_mode"]:
        reasons.append(f"invalid mode {data.mode} (only PAPER is tradable in V1)")

    checks["hard_reject"] = not data.hard_reject
    if data.hard_reject:
        reasons.append("analysis hard-reject present (no AI override possible)")

    # An open position with no usable mark makes equity and drawdown unknown.
    # Sizing off a partial book would understate risk, so this rejects outright.
    checks["valuation_complete"] = bool(data.valuation_complete)
    if not data.valuation_complete:
        reasons.append("open position valuation incomplete -> fail closed")

    numeric_pairs = {
        "equity": data.equity_usd,
        "reference_price": data.reference_price,
        "liquidity": data.liquidity_usd,
        "slippage": data.slippage_pct,
        "fee": data.fee_pct,
        "risk_reward": data.risk_reward,
        "market_data_age": data.market_data_age_seconds,
    }
    all_finite = True
    for name, value in numeric_pairs.items():
        ok = _finite(value)
        checks[f"finite_{name}"] = ok
        if not ok:
            all_finite = False
            reasons.append(f"mandatory metric '{name}' missing or non-finite -> fail closed")

    if not _finite(data.market_data_age_seconds) or (
        data.market_data_age_seconds > cfg["max_signal_age_seconds"]
    ):
        checks["data_fresh"] = False
        reasons.append("market data stale or unknown age -> fail closed")
    else:
        checks["data_fresh"] = True

    checks["slippage"] = (not _finite(data.slippage_pct)) or (
        data.slippage_pct <= cfg["max_slippage_pct"]
    )
    if not checks["slippage"]:
        reasons.append(f"slippage {data.slippage_pct:.2f}% > ceiling {cfg['max_slippage_pct']}%")

    checks["liquidity"] = _finite(data.liquidity_usd) and (
        data.liquidity_usd >= cfg["min_liquidity_usd"]
    )
    if _finite(data.liquidity_usd) and data.liquidity_usd < cfg["min_liquidity_usd"]:
        reasons.append(f"liquidity {data.liquidity_usd:.0f} < min {cfg['min_liquidity_usd']:.0f}")

    checks["fee"] = (not _finite(data.fee_pct)) or data.fee_pct <= cfg["max_fee_pct"]
    if not checks["fee"]:
        reasons.append(f"fee {data.fee_pct:.2f}% > max {cfg['max_fee_pct']}%")

    checks["price_impact"] = (not _finite(data.price_impact_pct)) or (
        data.price_impact_pct <= cfg["max_price_impact_pct"]
    )
    if not checks["price_impact"]:
        reasons.append(
            f"price impact {data.price_impact_pct:.2f}% > max {cfg['max_price_impact_pct']}%"
        )

    checks["risk_reward"] = (not _finite(data.risk_reward)) or (
        data.risk_reward >= cfg["min_risk_reward"]
    )
    if _finite(data.risk_reward) and data.risk_reward < cfg["min_risk_reward"]:
        reasons.append(f"risk/reward {data.risk_reward} < min {cfg['min_risk_reward']}")

    checks["max_positions"] = data.open_positions_count < cfg["max_concurrent_positions"]
    if not checks["max_positions"]:
        reasons.append("max concurrent positions reached")

    checks["daily_loss"] = data.daily_realized_pnl_usd > -abs(cfg["daily_loss_limit_usd"])
    if not checks["daily_loss"]:
        reasons.append(f"daily loss limit hit ({data.daily_realized_pnl_usd:.2f})")

    # Drawdown must fail closed. Previously an unknown or non-positive peak
    # skipped the check entirely and reported PASS, which is exactly the
    # "unknown became a green light" failure this gate exists to prevent.
    equity_known = _finite(data.equity_usd)
    peak_known = _finite(data.peak_equity_usd)
    if not equity_known or not peak_known:
        checks["drawdown"] = False
        reasons.append("equity or peak equity unknown -> drawdown cannot be verified -> fail closed")
    elif data.peak_equity_usd > 0:
        dd_pct = (data.peak_equity_usd - data.equity_usd) / data.peak_equity_usd * 100
        checks["drawdown"] = dd_pct < cfg["max_drawdown_pct"]
        if not checks["drawdown"]:
            reasons.append(f"drawdown {dd_pct:.1f}% >= max {cfg['max_drawdown_pct']}%")
    else:
        # A non-positive peak means the account has no buffer left. Any equity,
        # including a profit, is a total drawdown from zero capital.
        checks["drawdown"] = False
        reasons.append(
            f"peak equity {data.peak_equity_usd:.2f} is not positive -> drawdown cannot be verified -> fail closed"
        )

    if data.last_loss_at is not None:
        elapsed = (data.now - data.last_loss_at).total_seconds()
        checks["cooldown"] = elapsed >= cfg["cooldown_after_loss_seconds"]
        if not checks["cooldown"]:
            reasons.append("cooldown after recent loss not elapsed")
    else:
        checks["cooldown"] = True

    if data.signal_expires_at is not None and data.now > data.signal_expires_at:
        checks["signal_valid"] = False
        reasons.append("signal expired")
    else:
        checks["signal_valid"] = True

    approved = all(checks.values()) and all_finite
    sized: float | None = None
    if approved and _finite(data.equity_usd) and data.equity_usd > 0:
        pct_alloc = data.equity_usd * cfg["max_position_pct_of_equity"] / 100.0
        sized = min(cfg["max_position_allocation_usd"], pct_alloc)
        remaining_exposure = cfg["max_total_exposure_usd"] - data.open_exposure_usd
        sized = min(sized, max(0.0, remaining_exposure))
        if sized <= 0:
            approved = False
            reasons.append("no remaining exposure budget")

    return RiskDecision(
        approved=approved, reasons=reasons, checks=checks, sized_allocation_usd=sized
    )

