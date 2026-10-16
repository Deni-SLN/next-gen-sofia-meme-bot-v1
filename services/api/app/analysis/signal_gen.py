"""Signal generation (FR-AE-007). Signals are NOT orders."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.analysis.indicators import estimate_price_impact
from app.analysis.risk import RiskResult
from app.analysis.scoring import ScoreResult

STRATEGY_VERSION = "strategy-v1"

SIGNAL_STATUSES = [
    "CREATED", "VALIDATED", "WAIT", "REJECTED", "ACTIVE", "EXPIRED", "INVALIDATED", "EVALUATED",
]


@dataclass
class SignalPlan:
    decision: str  # LONG_CANDIDATE | BEARISH_BIAS | WAIT | REJECT
    reasons: list[str]
    entry_reference: float | None = None
    stop_reference: float | None = None
    target_references: list[float] | None = None
    risk_reward: float | None = None
    slippage_assumption: float | None = None
    fee_assumptions: dict = field(default_factory=dict)
    invalidation_conditions: list[str] = field(default_factory=list)


def generate_signal_plan(
    price: float | None,
    atr_value: float | None,
    support: float | None,
    resistance: float | None,
    structure: str | None,
    risk: RiskResult,
    score: ScoreResult,
    liquidity_usd: float | None,
    allocation_usd: float = 100.0,
    score_threshold_long: float = 60.0,
) -> SignalPlan:
    reasons = list(risk.reasons)

    if risk.hard_reject:
        reasons.append("hard-reject overrides aggregate score")
        return SignalPlan(
            decision="REJECT",
            reasons=reasons,
            invalidation_conditions=[],
        )

    if structure == "BREAKDOWN" or (score.components.get("trend_momentum") or 50) < 35:
        return SignalPlan(decision="BEARISH_BIAS", reasons=reasons + ["bearish structure/momentum"])

    if score.score is None or score.score < score_threshold_long or price is None:
        reasons.append(f"score {score.score} below threshold {score_threshold_long} or price unknown")
        return SignalPlan(decision="WAIT", reasons=reasons)

    if structure not in ("BREAKOUT", "RETEST"):
        reasons.append(f"structure {structure} not actionable")
        return SignalPlan(decision="WAIT", reasons=reasons)

    # Entry / stop / targets
    entry = price
    if atr_value is not None and atr_value > 0:
        stop = entry - 1.5 * atr_value
    elif support is not None and support < entry:
        stop = support * 0.995
    else:
        stop = entry * 0.93
    risk_per_unit = entry - stop
    if risk_per_unit <= 0:
        return SignalPlan(decision="WAIT", reasons=reasons + ["invalid stop placement"])
    t1 = entry + 2 * risk_per_unit
    t2 = entry + 3 * risk_per_unit
    rr = (t2 - entry) / risk_per_unit

    # Resistance directly above entry caps the first target, so the nominal
    # 2R/3R plan is not achievable and the trade should not be taken as-is.
    if resistance is not None and resistance > 0:
        room_to_resistance = (resistance - entry) / risk_per_unit
        if room_to_resistance <= 0:
            reasons.append(
                f"entry at or above nearest resistance {resistance:.6g}: no room for a long"
            )
            return SignalPlan(decision="WAIT", reasons=reasons)
        if room_to_resistance < 2.0:
            reasons.append(
                f"nearest resistance {resistance:.6g} only {room_to_resistance:.2f}R away: "
                "targets capped, risk/reward reduced"
            )
            t1 = min(t1, resistance)
            t2 = min(t2, resistance)
            rr = (t2 - entry) / risk_per_unit
            if rr < 1.5:
                reasons.append(f"risk/reward {rr:.2f} below minimum after resistance cap")
                return SignalPlan(decision="WAIT", reasons=reasons)

    impact = estimate_price_impact(allocation_usd, liquidity_usd)
    if impact is not None and impact > 0.03:
        reasons.append(f"estimated price impact {impact:.1%} too high for allocation")
        return SignalPlan(decision="WAIT", reasons=reasons)

    slippage = round(min(0.02, impact or 0.005), 6)
    fee_assumptions = {"taker_fee_pct": 0.003, "note": "assumed DEX fee + priority"}
    invalidations = [
        f"closes below {stop:.6g} on the signal timeframe",
        "liquidity drops more than 40% from signal snapshot",
        "signal passes expiry before entry",
        "risk flags escalate to hard-reject",
    ]
    reasons.append(f"bullish {structure}, score {score.score:.1f}, RR ~{rr:.2f}")
    return SignalPlan(
        decision="LONG_CANDIDATE",
        reasons=reasons,
        entry_reference=entry,
        stop_reference=stop,
        target_references=[t1, t2],
        risk_reward=round(rr, 3),
        slippage_assumption=slippage,
        fee_assumptions=fee_assumptions,
        invalidation_conditions=invalidations,
    )


def compute_signature(payload: dict) -> str:
    from app.core.security import internal_signature

    return internal_signature(json.dumps(payload, sort_keys=True, default=str))


def signal_expiry(created_at: datetime, ttl_minutes: int = 30) -> datetime:
    return created_at + timedelta(minutes=ttl_minutes)
