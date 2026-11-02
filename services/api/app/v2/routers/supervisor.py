"""
FastAPI Router for SOFIA MEME BOT V2 Trade Supervisor.
Satisfies PRD Section 8 (Trade Supervisor) & Section 13 (Supervisor API).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.v2.ai.orchestrator import orchestrator
from app.v2.agents.registry import agent_registry
from app.v2.db.models import PositionEvent
from app.db.models import PortfolioHolding, Trade, BotState
from app.v2.core.supervisor import trade_supervisor
from app.v2.core.position_state_machine import position_state_machine
from app.v2.core.conflict_resolver import conflict_resolver
from app.v2.services.live_executor import V2LiveExecutor

router = APIRouter(tags=["V2 Trade Supervisor"])


class KillSwitchRequest(BaseModel):
    engage: bool
    reason: str = "MANUAL_OPERATOR_COMMAND"


class ConflictResolutionRequest(BaseModel):
    entry_decision: Optional[str] = "BUY"
    risk_veto: bool = False
    veto_reason: Optional[str] = None
    is_stale_data: bool = False
    ai_provider_available: bool = True
    current_open_positions: int = 0
    max_open_positions: int = 5
    daily_drawdown_limit_hit: bool = False


class SuperviseTickRequest(BaseModel):
    strategy_mode: str = "DEFAULT"
    mode: str = "PAPER"


@router.get("/status")
def get_supervisor_status(db: Session = Depends(get_db)):
    """
    Central status of the autonomous trading system:
    - Multi-agent coordination state
    - AI circuit breaker & health
    - Real-time active positions & risk controls
    """
    # Check active positions count across PAPER and LIVE
    active_paper = db.execute(
        select(func.count(PortfolioHolding.id)).where(PortfolioHolding.mode == "PAPER", PortfolioHolding.quantity > 0)
    ).scalar() or 0
    active_live = db.execute(
        select(func.count(PortfolioHolding.id)).where(PortfolioHolding.mode == "LIVE", PortfolioHolding.quantity > 0)
    ).scalar() or 0

    # Bot state
    bot_state = db.execute(select(BotState).order_by(BotState.id.desc()).limit(1)).scalar_one_or_none()
    bot_status = bot_state.status if bot_state else "idle"

    # Today's realized PnL from closed sell trades (Zero Dummy Data)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl = db.execute(
        select(func.sum(Trade.pnl)).where(
            Trade.status == "closed",
            Trade.side == "sell",
            Trade.closed_at >= today_start,
        )
    ).scalar() or 0.0

    system_status = "operational"
    if orchestrator.circuit_breaker.is_open:
        system_status = "degraded"
    if bot_status in ("stopped", "error"):
        system_status = "halted"

    return {
        "agent": "trade_supervisor",
        "system_status": system_status,
        "engine_mode": bot_state.mode if bot_state else "PAPER",
        "bot_status": bot_status,
        "ai_service_online": not orchestrator.circuit_breaker.is_open,
        "deterministic_risk_online": True,
        "kill_switch_engaged": (bot_status == "stopped"),
        "circuit_breaker_active": orchestrator.circuit_breaker.is_open,
        "active_positions": {
            "paper": active_paper,
            "live": active_live,
            "total": active_paper + active_live,
        },
        "daily_realized_pnl_usd": round(float(today_pnl), 4),
        "registered_agents": agent_registry.list_agents(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/events")
def list_supervisor_events(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieves recent lifecycle position and supervision events."""
    rows = (
        db.execute(select(PositionEvent).order_by(desc(PositionEvent.created_at)).limit(limit))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "events": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "mint": r.mint,
                "mode": r.mode,
                "event_type": r.event_type,
                "quantity": r.quantity,
                "price": r.price,
                "realized_pnl_usd": r.realized_pnl_usd,
                "tx_hash": r.tx_hash,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/positions")
def list_tracked_positions(
    mode: Optional[str] = Query(default=None, description="PAPER or LIVE"),
):
    """Retrieves state-machine status and lifecycle transitions for all monitored positions."""
    positions = position_state_machine.list_positions(mode=mode)
    return {
        "count": len(positions),
        "positions": [p.model_dump() for p in positions],
    }


@router.post("/tick")
def execute_supervision_tick(
    req: SuperviseTickRequest,
    db: Session = Depends(get_db),
):
    """Executes an autonomous monitoring tick across all active holdings."""
    results = trade_supervisor.supervise_positions_tick(
        db=db,
        strategy_mode=req.strategy_mode,
        mode=req.mode,
    )
    return {
        "status": "success",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "positions_evaluated": len(results),
        "results": results,
    }


@router.post("/resolve-conflict")
def evaluate_conflict_resolution(req: ConflictResolutionRequest):
    """Audits and arbitrates a potential conflict between entry/exit agents and risk rules."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision=req.entry_decision or "BUY",
        risk_veto=req.risk_veto,
        veto_reason=req.veto_reason,
        is_stale_data=req.is_stale_data,
        ai_provider_available=req.ai_provider_available,
        current_open_positions=req.current_open_positions,
        max_open_positions=req.max_open_positions,
        daily_drawdown_limit_hit=req.daily_drawdown_limit_hit,
    )
    return out.model_dump()


@router.post("/kill-switch")
def toggle_emergency_kill_switch(req: KillSwitchRequest):
    """Engages or disengages global autonomous emergency stop."""
    if req.engage:
        trade_supervisor.engage_kill_switch(reason=req.reason)
    else:
        trade_supervisor.disengage_kill_switch()
    return {
        "kill_switch_engaged": trade_supervisor._kill_switch_engaged,
        "circuit_breaker_active": trade_supervisor._circuit_breaker_active,
        "status": "halted" if req.engage else "operational",
    }


@router.post("/recover")
def recover_positions_from_db(
    mode: str = Query(default="PAPER"),
    db: Session = Depends(get_db),
):
    """Rebuilds position state-machine tracking and excursion levels after server reload."""
    recovered = trade_supervisor.recover_positions_after_restart(db=db, mode=mode)
    return {
        "status": "success",
        "recovered_positions_count": recovered,
        "last_reconciled_at": trade_supervisor._last_reconciled_at,
    }


# -------------------------------------------------------------------------
# Phase 7: Controlled LIVE Deployment & Pre-Flight Endpoints
# -------------------------------------------------------------------------

class AuthorizeLiveRequest(BaseModel):
    authority: str = "DSLN Capital CEO"
    confirmation_code: str = "DSLN-LIVE-AUTHORIZATION-CONFIRMED"


class RevokeLiveRequest(BaseModel):
    reason: str = "OPERATOR_MANUAL_HALT"


@router.get("/live/preflight")
def get_live_preflight_audit(
    requested_sol: float = Query(0.02, ge=0.005, le=0.10, description="Requested trade allocation in SOL"),
):
    """
    Phase 7 Pre-Flight Safety Audit:
    Verifies Solana wallet connection, live SOL balance, 0.05 SOL gas reserve invariant,
    allocation ceiling, and executive authorization status.
    """
    return V2LiveExecutor.run_preflight_checks(requested_sol=requested_sol)


@router.get("/live/status")
def get_live_deployment_status():
    """
    Phase 7 Controlled LIVE Deployment Status:
    Returns authorization state, hardware risk parameters, allocation caps, and kill-switch telemetry.
    """
    preflight = V2LiveExecutor.run_preflight_checks(requested_sol=0.02)
    return {
        "phase": "PHASE_7_CONTROLLED_LIVE",
        "is_authorized": V2LiveExecutor.is_authorized(),
        "authorized_by": V2LiveExecutor._authorized_by,
        "authorized_at": V2LiveExecutor._authorization_timestamp,
        "supervisor_kill_switch_engaged": trade_supervisor._kill_switch_engaged,
        "supervisor_circuit_breaker_active": trade_supervisor._circuit_breaker_active,
        "min_sol_reserve": V2LiveExecutor.MIN_SOL_RESERVE,
        "max_canary_allocation_sol": V2LiveExecutor.MAX_CANARY_ALLOCATION_SOL,
        "max_canary_allocation_usd": V2LiveExecutor.MAX_CANARY_ALLOCATION_USD,
        "max_permitted_slippage_bps": V2LiveExecutor.MAX_PERMITTED_SLIPPAGE_BPS,
        "wallet_telemetry": {
            "wallet_pubkey": preflight.get("wallet_pubkey"),
            "sol_balance": preflight.get("sol_balance"),
            "available_trading_sol": preflight.get("available_trading_sol"),
            "rpc_endpoint": preflight.get("rpc_endpoint"),
        },
    }


@router.post("/live/authorize")
def authorize_live_deployment(req: AuthorizeLiveRequest):
    """
    Unlocks Controlled LIVE Trading (requires valid confirmation code).
    """
    try:
        return V2LiveExecutor.authorize_live_deployment(
            authority=req.authority,
            confirmation_code=req.confirmation_code,
        )
    except ValueError as err:
        raise HTTPException(status_code=403, detail=str(err))


@router.post("/live/revoke")
def revoke_live_deployment(req: RevokeLiveRequest):
    """
    Revokes LIVE trading authorization immediately, restoring system to safe/locked state.
    """
    return V2LiveExecutor.revoke_live_deployment(reason=req.reason)

