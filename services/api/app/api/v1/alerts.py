"""Alert rules and delivery endpoints (PRD §15, FR §12.6).

Read paths are available to any authenticated actor; anything that sends or
changes state requires an operator.
"""

from app.api.v1.deps import current_actor, require_operator
from app.core.config import settings
from app.db.session import get_db
from app.models.ops import AlertDelivery
from app.services import alert_service
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    db: Session = Depends(get_db),
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    q = db.query(AlertDelivery)
    if status:
        q = q.filter(AlertDelivery.delivery_status == status)
    total = q.count()
    rows = q.order_by(AlertDelivery.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": a.id,
                "dedup_key": a.dedup_key,
                "title": a.title,
                "body": a.body,
                "channel": a.channel,
                "delivery_status": a.delivery_status,
                "attempt_count": a.attempt_count,
                "reference_type": a.reference_type,
                "reference_id": a.reference_id,
                "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


@router.post("/evaluate")
def evaluate_now(
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    """Evaluate the standing rules without sending anything."""
    return alert_service.evaluate_alert_rules(db)


@router.post("/flush")
def flush_now(
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    """Attempt delivery of everything queued."""
    return alert_service.flush_pending(db)


@router.post("/{alert_id}/deliver")
def deliver_now(
    alert_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    row = db.query(AlertDelivery).filter(AlertDelivery.id == alert_id).first()
    if row is None:
        return {"ok": False, "reason": "alert not found"}
    alert = alert_service.Alert(
        dedup_key=row.dedup_key,
        title=row.title or "",
        body=row.body or "",
        reference_type=row.reference_type,
        reference_id=row.reference_id,
    )
    return alert_service.deliver(db, alert.id, alert)
