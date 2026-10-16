"""Portfolio & accounting endpoints (FR §12.5).

PAPER and LIVE are separated. LIVE is unavailable in V1 and clearly marked.
"""

from app.accounting.equity import equity_curve, record_event, summarize_mode
from app.accounting.valuation import refresh_open_positions
from app.api.v1.deps import current_actor, require_operator
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.trading import AccountingEvent, Fill, OrderIntent, Position
from app.services.audit_service import write_audit
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

log = get_logger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

MODES = ("PAPER", "LIVE")


def _initial_capital(db: Session) -> float:
    from app.services.bot_service import get_initial_capital

    return float(get_initial_capital(db))


def _num(value: float | None, digits: int = 6) -> float | None:
    """Round for display, preserving None as None.

    An unmeasured value must reach the UI as null so it renders as unknown,
    not as 0 and not as a zero-decimal float.
    """
    return None if value is None else round(value, digits)


@router.get("/overview")
def overview(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    """Equity + PnL split by mode. LIVE clearly marked unavailable in V1."""
    cap = _initial_capital(db)
    out = {"modes": {}, "live_trading_enabled": False, "note": "LIVE is disabled for this release."}
    for mode in MODES:
        snap = summarize_mode(db, mode, cap)
        out["modes"][mode] = {
            "initial_capital": snap.initial_capital,
            "realized_pnl": _num(snap.realized_pnl),
            "unrealized_pnl": _num(snap.unrealized_pnl),
            "external_cash_movements": _num(snap.external_cash_movements),
            "equity": _num(snap.equity),
            "high_water_mark": _num(snap.high_water_mark),
            "current_drawdown_pct": _num(snap.current_drawdown_pct, 4),
            # Always present so the operator can see the floor even when the
            # book cannot be fully valued.
            "known_unrealized_pnl": _num(snap.known_unrealized_pnl),
            "known_equity": _num(snap.known_equity),
            "valuation_status": snap.valuation_status,
            "unmarked_positions": snap.unmarked_positions,
            "available": mode == "PAPER" and snap.is_complete,
        }
    return out


@router.get("/positions")
def positions(
    db: Session = Depends(get_db),
    status: str | None = None,
    mode: str = "PAPER",
    actor: str = Depends(current_actor),
):
    # Refresh the marks before reading. Serving a stored valuation that may
    # predate the latest snapshot is how the "an open position is worth exactly
    # cost basis" defect hid.
    refresh_open_positions(db, mode)
    q = db.query(Position).filter(Position.mode == mode)
    if status:
        q = q.filter(Position.status == status)
    rows = q.order_by(Position.opened_at.desc()).all()
    return {
        "mode": mode,
        "items": [
            {
                "id": p.id,
                "mint_address": p.mint_address,
                "status": p.status,
                "quantity": p.quantity,
                "average_entry_price": p.average_entry_price,
                "total_fees": p.total_fees,
                "realized_pnl": p.realized_pnl,
                "unrealized_pnl": p.unrealized_pnl,
                "mark_price": p.mark_price,
                "valuation_status": p.valuation_status,
                "valuation_reason": p.valuation_reason,
                "valuation_as_of": p.valuation_as_of.isoformat() if p.valuation_as_of else None,
                "exit_price": p.exit_price,
                "close_reason": p.close_reason,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in rows
        ],
    }


@router.get("/fees-slippage")
def fees_slippage(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    # Fills are only created by PAPER execution in V1; slippage is embedded in fill price.
    fills = db.query(Fill).all()
    total_fee = sum(f.fee_amount or 0.0 for f in fills)
    total_slip = sum(f.slippage or 0.0 for f in fills)
    avg_slip = (total_slip / len(fills)) if fills else None
    return {
        "fills": len(fills),
        "total_fees_usd": round(total_fee, 6),
        "avg_slippage_pct": round(avg_slip * 100, 4) if avg_slip is not None else None,
        "note": "Slippage is embedded in simulated fill prices and stored per-fill; LIVE unavailable in V1.",
    }




@router.post("/cash-movement")
def cash_movement(payload: dict, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Record an external deposit/withdrawal. Only PAPER in V1.

    Ledger convention: positive amount = money leaving (withdrawal);
    negative = money entering (deposit). See accounting.equity docstring.
    """
    mode = (payload or {}).get("mode", "PAPER")
    kind = str((payload or {}).get("kind", (payload or {}).get("movement", ""))).upper()
    amount = (payload or {}).get("amount")
    if mode not in MODES or mode == "LIVE":
        raise ValidationError("cash movements are only available in PAPER mode for V1")
    if kind not in ("DEPOSIT", "WITHDRAWAL"):  # DEPOSIT | WITHDRAWAL
        raise ValidationError("kind must be DEPOSIT or WITHDRAWAL")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValidationError("amount must be a positive number")
    sign = 1.0 if kind == "WITHDRAWAL" else -1.0
    ev = record_event(
        db,
        mode,
        kind,
        amount=sign * abs(float(amount)),
        reference_type="external",
        idempotency_key=f"cash:{mode}:{kind}:{abs(float(amount))}:{actor}",
    )
    if ev is None:
        return {"recorded": False, "reason": "duplicate cash movement suppressed (idempotency)"}
    write_audit(actor, "cash_movement", "accounting_event", ev.id, {"mode": mode, "kind": kind}, db)
    return {"recorded": True, "id": ev.id, "mode": mode, "kind": kind, "amount": ev.amount}


@router.get("/accounting-audit")
def accounting_audit(
    db: Session = Depends(get_db),
    mode: str = "PAPER",
    actor: str = Depends(current_actor),
):
    """Recompute equity from the append-only ledger to prove formula integrity."""
    cap = _initial_capital(db)
    snap = summarize_mode(db, mode, cap)
    if snap.equity is None:
        # The formula cannot be checked against an unknown equity; saying it is
        # "consistent" would be asserting something that was never computed.
        return {
            "mode": mode,
            "formula": "equity = initial_capital + realized_pnl + unrealized_pnl - external_cash_movements",
            "initial_capital": snap.initial_capital,
            "realized_pnl": _num(snap.realized_pnl),
            "unrealized_pnl": None,
            "external_cash_movements": _num(snap.external_cash_movements),
            "equity": None,
            "recomputed_equity": None,
            "consistent": None,
            "valuation_status": snap.valuation_status,
            "unmarked_positions": snap.unmarked_positions,
            "reason": "open positions are not fully valued; equity is unknown, not zero",
        }
    expected = cap + snap.realized_pnl + snap.unrealized_pnl - snap.external_cash_movements
    return {
        "mode": mode,
        "formula": "equity = initial_capital + realized_pnl + unrealized_pnl - external_cash_movements",
        "initial_capital": snap.initial_capital,
        "realized_pnl": _num(snap.realized_pnl),
        "unrealized_pnl": _num(snap.unrealized_pnl),
        "external_cash_movements": _num(snap.external_cash_movements),
        "equity": _num(snap.equity),
        "recomputed_equity": _num(expected),
        "consistent": abs(snap.equity - expected) < 1e-6,
        "valuation_status": snap.valuation_status,
        "unmarked_positions": snap.unmarked_positions,
    }



@router.get("/transactions")
def transactions(
    db: Session = Depends(get_db),
    mode: str = "PAPER",
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(AccountingEvent).filter(AccountingEvent.mode == mode)
    total = q.count()
    rows = q.order_by(AccountingEvent.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "mode": mode,
        "items": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "amount": e.amount,
                "asset": e.asset,
                "reference_type": e.reference_type,
                "reference_id": e.reference_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/orders")
def portfolio_orders(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    """All order intents (PAPER only in V1) with linked fill info."""
    q = db.query(OrderIntent)
    total = q.count()
    rows = q.order_by(OrderIntent.created_at.desc()).offset(offset).limit(limit).all()
    items = []
    for o in rows:
        fills = db.query(Fill).filter(Fill.order_id == o.id).all()
        items.append(
            {
                "id": o.id,
                "signal_id": o.signal_id,
                "mode": o.mode,
                "side": o.side,
                "requested_size": o.requested_size,
                "reference_price": o.reference_price,
                "risk_decision": o.risk_decision,
                "risk_reasons": o.risk_reasons,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "fills": [
                    {
                        "id": f.id,
                        "fill_quantity": f.fill_quantity,
                        "fill_price": f.fill_price,
                        "fee_amount": f.fee_amount,
                        "slippage": f.slippage,
                        "fill_type": f.fill_type,
                        "filled_at": f.filled_at.isoformat() if f.filled_at else None,
                    }
                    for f in fills
                ],
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/equity-curve")
def equity_curve_endpoint(
    db: Session = Depends(get_db),
    mode: str = "PAPER",
    actor: str = Depends(current_actor),
):
    cap = _initial_capital(db)
    return {"mode": mode, "initial_capital": cap, "curve": equity_curve(db, mode, cap)}
