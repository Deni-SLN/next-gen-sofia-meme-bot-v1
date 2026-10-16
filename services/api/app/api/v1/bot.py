"""Trading bot control & risk config endpoints (FR §12.4).

LIVE start is rejected server-side regardless of request (V1 gate).
"""

from app.api.v1.deps import current_actor, require_operator
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_db
from app.models.trading import BotRun, OrderIntent, Position
from app.services import bot_service
from app.services.audit_service import write_audit
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/bot", tags=["bot"])
risk_router = APIRouter(prefix="/risk", tags=["risk"])


class StartBody(BaseModel):
    mode: str | None = None  # PAPER | ANALYSIS_ONLY (LIVE always rejected)


@router.get("/status")
def bot_status(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    return bot_service.get_bot_state(db)


@router.post("/start")
def bot_start(
    payload: StartBody | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    mode = payload.mode if payload else None
    return bot_service.start_bot(db, actor, mode=mode)


@router.post("/pause")
def bot_pause(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return bot_service.pause_bot(db, actor)


@router.post("/resume")
def bot_resume(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return bot_service.resume_bot(db, actor)


@router.post("/stop")
def bot_stop(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    reason = (payload or {}).get("reason", "operator stop")
    return bot_service.stop_bot(db, actor, reason=reason)


@router.post("/emergency-stop")
def bot_emergency_stop(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return bot_service.emergency_stop(db, actor)


@router.post("/clear-kill-switch")
def bot_clear_kill_switch(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    return bot_service.clear_kill_switch(db, actor)


def _order_json(o: OrderIntent) -> dict:
    return {
        "id": o.id,
        "bot_run_id": o.bot_run_id,
        "signal_id": o.signal_id,
        "mode": o.mode,
        "side": o.side,
        "requested_size": o.requested_size,
        "reference_price": o.reference_price,
        "risk_decision": o.risk_decision,
        "risk_reasons": o.risk_reasons,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _position_json(db: Session, p: Position) -> dict:
    from app.services.position_manager import ExitPlan, exit_plan

    try:
        plan = exit_plan(db, p)
    except Exception:  # noqa: BLE001 - serialising a position must not raise
        plan = ExitPlan(source="UNAVAILABLE")
    return {
        "id": p.id,
        "bot_run_id": p.bot_run_id,
        "mode": p.mode,
        "token_id": p.token_id,
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
        "exit_stop_price": plan.stop_price,
        "exit_target_prices": list(plan.target_prices),
        "exit_plan_source": plan.source,
        "exit_price": p.exit_price,
        "close_reason": p.close_reason,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
    }

@router.get("/runs")
def bot_runs(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(BotRun)
    total = q.count()
    rows = q.order_by(BotRun.started_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "mode": r.mode,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "stopped_at": r.stopped_at.isoformat() if r.stopped_at else None,
                "started_by": r.started_by,
                "stop_reason": r.stop_reason,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}")
def bot_run(run_id: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    r = db.get(BotRun, run_id)
    if r is None:
        raise NotFoundError("bot_run", run_id)
    orders = db.query(OrderIntent).filter(OrderIntent.bot_run_id == run_id).all()
    positions = db.query(Position).filter(Position.bot_run_id == run_id).all()
    return {
        "id": r.id,
        "mode": r.mode,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "stopped_at": r.stopped_at.isoformat() if r.stopped_at else None,
        "started_by": r.started_by,
        "stop_reason": r.stop_reason,
        "orders": [_order_json(o) for o in orders],
        "positions": [_position_json(db, p) for p in positions],
    }


@router.get("/orders")
def bot_orders(
    db: Session = Depends(get_db),
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(OrderIntent)
    if status:
        q = q.filter(OrderIntent.status == status)
    total = q.count()
    rows = q.order_by(OrderIntent.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_order_json(o) for o in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/positions")
def bot_positions(
    db: Session = Depends(get_db),
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(Position)
    if status:
        q = q.filter(Position.status == status)
    total = q.count()
    rows = q.order_by(Position.opened_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_position_json(db, p) for p in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/positions/{position_id}/close")
def close_position(
    position_id: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    from app.services.trading_service import close_position as _close

    reason = (payload or {}).get("reason", "operator_close")
    result = _close(db, position_id, reason)
    write_audit(actor, "close_position", "position", position_id, {"reason": reason}, db)
    return result


@router.post("/positions/lifecycle")
def run_position_lifecycle_now(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    """Run the TP/SL sweep on demand.

    PAPER only, always. `dry_run` (default true) reports what would close and
    why, including the positions that are being held because their mark is
    missing or stale - which is the case an operator most needs to see.
    """
    from app.services.position_manager import run_position_lifecycle

    body = payload or {}
    mode = str(body.get("mode", "PAPER")).upper()
    dry_run = bool(body.get("dry_run", True))
    result = run_position_lifecycle(db, mode=mode, dry_run=dry_run)
    write_audit(
        actor,
        "position_lifecycle",
        "bot",
        None,
        {"mode": mode, "dry_run": dry_run, "closed": len(result.get("closed", []))},
        db,
    )
    return result


# ----------------------------- Risk config -----------------------------


@risk_router.get("/config")
def get_risk_config(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    return bot_service.get_risk_config(db)


@risk_router.put("/config")
def update_risk_config(
    payload: dict,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    if not isinstance(payload, dict) or not payload:
        raise ValidationError("config body required")
    bot_service.set_risk_config(db, payload)
    write_audit(actor, "update_risk_config", "risk", None, {"keys": sorted(payload)}, db)
    return bot_service.get_risk_config(db)

