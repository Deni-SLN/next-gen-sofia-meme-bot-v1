"""
FastAPI Router for SOFIA MEME BOT V2 Trade Supervisor.
Satisfies PRD Section 8 (Trade Supervisor) & Section 13 (Supervisor API).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.v2.ai.orchestrator import orchestrator
from app.v2.agents.registry import agent_registry
from app.v2.db.models import PositionEvent
from app.db.models import PortfolioHolding, Trade, BotState

router = APIRouter(tags=["V2 Trade Supervisor"])


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
