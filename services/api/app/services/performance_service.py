"""Performance metrics computed from the same ledger/events (§14).

Formulas follow the PRD exactly. Undefined results (e.g. profit factor when
gross loss is 0) are returned as None, never fabricated numbers.

Drawdown is read from the canonical equity model rather than recomputed here,
so Performance and Portfolio cannot report two different drawdowns for the same
account. Metrics the pipeline cannot yet measure are published as explicit
`null`s and listed in `unavailable_metrics`, so a caller can tell "not
measured" apart from "measured as zero" without reading this source.
"""

import math

from sqlalchemy.orm import Session

from app.models.trading import AccountingEvent, Position

# PRD §14 requires these; the signal-evaluation pipeline that produces them is
# still a placeholder, so they are declared rather than silently omitted.
UNAVAILABLE_METRICS = ("mae_avg", "mfe_avg")


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def compute_performance(db: Session, mode: str) -> dict:
    from app.accounting.equity import summarize_mode
    from app.services.bot_service import get_initial_capital

    closed = (
        db.query(Position)
        .filter(Position.mode == mode, Position.status == "CLOSED")
        .all()
    )
    n = len(closed)
    wins = [p for p in closed if p.realized_pnl > 0]
    losses = [p for p in closed if p.realized_pnl < 0]
    win_rate = (len(wins) / n) if n else None
    avg_win = (sum(p.realized_pnl for p in wins) / len(wins)) if wins else None
    avg_loss = (abs(sum(p.realized_pnl for p in losses)) / len(losses)) if losses else None
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    elif win_rate is not None and avg_win is not None and not losses:
        expectancy = win_rate * avg_win

    gross_profit = sum(p.realized_pnl for p in wins) if wins else 0.0
    gross_loss = sum(p.realized_pnl for p in losses) if losses else 0.0
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None

    fees = sum(
        e.amount
        for e in db.query(AccountingEvent)
        .filter(AccountingEvent.mode == mode, AccountingEvent.event_type == "FEE")
        .all()
    )

    # Drawdown and equity come from the one canonical model. An unvalued open
    # position makes them unknown; that propagates instead of reading as 0.
    snapshot = summarize_mode(db, mode, float(get_initial_capital(db)))
    drawdown_usd = (
        None if snapshot.equity is None else round(snapshot.high_water_mark - snapshot.equity, 4)
    )

    return {
        "mode": mode,
        "closed_positions": n,
        "open_positions": db.query(Position).filter(Position.mode == mode, Position.status == "OPEN").count(),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_win": round(avg_win, 4) if avg_win is not None else None,
        "avg_loss": round(avg_loss, 4) if avg_loss is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "total_fees": round(fees, 4),
        "net_realized_pnl": round(gross_profit + gross_loss, 4),
        "equity": snapshot.equity,
        "high_water_mark": round(snapshot.high_water_mark, 4),
        "max_drawdown_usd": drawdown_usd,
        "current_drawdown_pct": snapshot.current_drawdown_pct,
        "valuation_status": snapshot.valuation_status,
        "unmarked_positions": snapshot.unmarked_positions,
        # Declared, not fabricated. See UNAVAILABLE_METRICS.
        "mae_avg": None,
        "mfe_avg": None,
        "unavailable_metrics": list(UNAVAILABLE_METRICS),
    }
