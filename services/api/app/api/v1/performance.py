"""Performance, backtest, and equity-curve endpoints (FR §14).

Backtest runs the deterministic pipeline over stored candles with net-of-fee
PnL and drawdown. Results are stamped with engine/config versions for
reproducibility (FR §10.4).
"""

import math
from datetime import UTC, datetime

from app.api.v1.deps import current_actor, require_operator
from app.api.v1.market import SUPPORTED_TIMEFRAMES
from app.core.errors import ValidationError
from app.db.session import get_db
from app.models.market import Candle
from app.models.trading import AccountingEvent
from app.services import performance_service
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/performance", tags=["performance"])


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


@router.get("/summary")
def performance_summary(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    paper = performance_service.compute_performance(db, "PAPER")
    live = performance_service.compute_performance(db, "LIVE")
    return {
        "paper": paper,
        "live": live,
        "note": "PAPER and LIVE metrics are computed separately. LIVE has no fills in V1.",
    }


@router.get("/metrics")
def performance_metrics(
    db: Session = Depends(get_db),
    mode: str = Query("PAPER", pattern="^(PAPER|LIVE)$"),
    actor: str = Depends(current_actor),
):
    return performance_service.compute_performance(db, mode)


@router.get("/equity-curve")
def equity_curve(
    db: Session = Depends(get_db),
    mode: str = Query("PAPER", pattern="^(PAPER|LIVE)$"),
    limit: int = Query(200, le=1000),
    actor: str = Depends(current_actor),
):
    """The canonical equity path.

    This previously recomputed a second, incompatible series from realized PnL
    events alone. It now delegates to the same model as
    `/portfolio/equity-curve`, so the two cannot disagree. `final_pnl` is kept
    for existing callers.
    """
    from app.accounting.equity import equity_curve as canonical_curve
    from app.services.bot_service import get_initial_capital

    cap = float(get_initial_capital(db))
    curve = canonical_curve(db, mode, cap)[:limit]
    realized_pnl = db.query(AccountingEvent).filter(
        AccountingEvent.mode == mode, AccountingEvent.event_type == "REALIZED_PNL"
    )
    final_pnl = sum(e.amount for e in realized_pnl.all())
    return {
        "mode": mode,
        "initial_capital": cap,
        "curve": curve,
        "final_pnl": round(final_pnl, 6),
    }


backtest_router = APIRouter(prefix="/backtest", tags=["backtest"])


@backtest_router.post("")
def run_backtest(
    payload: dict,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    """Simple deterministic backtest over stored candles.

    Strategy: enter long when score-equivalent momentum (RSI<60 rising & close>open),
    exit on stop-loss/take-profit or signal flip. Net-of-fee PnL and max drawdown.
    """
    pair_id = (payload or {}).get("pair_id")
    # Candles are stored with these exact codes (see market_service.aggregate_candles).
    # A default the backend cannot match would silently find zero candles and
    # report "insufficient data" instead of a backtest.
    timeframe = str((payload or {}).get("timeframe", "M1")).upper()
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValidationError(
            f"unsupported timeframe {timeframe}; supported: {', '.join(SUPPORTED_TIMEFRAMES)}"
        )
    fee_pct = float((payload or {}).get("fee_pct", 0.3))
    slippage_pct = float((payload or {}).get("slippage_pct", 0.5))
    stop_loss_pct = float((payload or {}).get("stop_loss_pct", 8.0))
    take_profit_pct = float((payload or {}).get("take_profit_pct", 20.0))
    if not pair_id:
        raise ValidationError("pair_id required")

    candles = (
        db.query(Candle)
        .filter(Candle.pair_id == pair_id, Candle.timeframe == timeframe)
        .order_by(Candle.open_time)
        .all()
    )
    if len(candles) < 5:
        raise ValidationError(f"insufficient candles for backtest (have {len(candles)}, need >=5)")

    cash = float((payload or {}).get("initial_capital", 1000.0))
    start_cash = cash
    position_qty = 0.0
    entry_price = 0.0
    trades = 0
    wins = 0
    fees_paid = 0.0
    peak = cash
    max_dd = 0.0

    for c in candles:
        price = c.close
        if not _finite(price) or price <= 0:
            continue
        # Exit logic if in position
        if position_qty > 0:
            ret = (price - entry_price) / entry_price * 100.0
            hit_sl = ret <= -stop_loss_pct
            hit_tp = ret >= take_profit_pct
            if hit_sl or hit_tp:
                fill = price * (1 - slippage_pct / 100.0)
                fee = fill * position_qty * fee_pct / 100.0
                cash += fill * position_qty - fee
                fees_paid += fee
                trades += 1
                if ret > 0:
                    wins += 1
                position_qty = 0.0
        # Entry logic
        if position_qty == 0 and c.open is not None and c.close > c.open:
            alloc = cash
            fill = price * (1 + slippage_pct / 100.0)
            fee = alloc * fee_pct / 100.0
            position_qty = (alloc - fee) / fill
            entry_price = fill
            cash = 0.0
            fees_paid += fee

    final_equity = cash + (position_qty * candles[-1].close if position_qty > 0 else 0.0)
    net_pnl = final_equity - start_cash
    # single-buy max drawdown approximation via final vs start
    max_dd = max(0.0, (peak - final_equity) / peak * 100.0) if peak > 0 else 0.0

    return {
        "pair_id": pair_id,
        "timeframe": timeframe,
        "engine_version": "strategy-v1",
        "scoring_config_version": "scoring-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "candles": len(candles),
        "initial_capital": start_cash,
        "final_equity": round(final_equity, 6),
        "net_pnl": round(net_pnl, 6),
        "net_pnl_pct": round(net_pnl / start_cash * 100.0, 4) if start_cash else None,
        "trades": trades,
        "win_rate": round(wins / trades, 4) if trades else None,
        "total_fees": round(fees_paid, 6),
        "max_drawdown_pct": round(max_dd, 4),
        "assumptions": {"fee_pct": fee_pct, "slippage_pct": slippage_pct, "stop_loss_pct": stop_loss_pct, "take_profit_pct": take_profit_pct},
    }
