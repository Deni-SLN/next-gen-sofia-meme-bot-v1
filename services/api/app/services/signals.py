from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.models import Signal


def list_signals(db: Session, status: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[Signal], int]:
    stmt = select(Signal)
    count_stmt = select(func.count()).select_from(Signal)
    if status:
        stmt = stmt.where(Signal.status == status)
        count_stmt = count_stmt.where(Signal.status == status)
    total = db.execute(count_stmt).scalar() or 0
    stmt = stmt.order_by(Signal.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def create_signal(db: Session, data: dict) -> Signal:
    sig = Signal(
        symbol=data["symbol"],
        direction=data["direction"],
        confidence=float(data.get("confidence", 0.0)),
        source=data.get("source", "AI_ENGINE"),
        timeframe=data.get("timeframe", "1h"),
        entry_price=data.get("entry_price"),
        stop_loss=data.get("stop_loss"),
        take_profit=data.get("take_profit"),
        status=data.get("status", "pending"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig


def update_signal_status(db: Session, signal_id: int, status: str) -> Signal:
    sig = db.execute(select(Signal).where(Signal.id == signal_id)).scalar_one_or_none()
    if not sig:
        raise ValueError("SIGNAL_NOT_FOUND")
    sig.status = status
    db.commit()
    db.refresh(sig)
    return sig
