"""Audit log writer (FR §16). All sensitive changes go through here.

Audit rows MUST land in the same transaction as the change they describe.
Pass the caller's `db` session whenever one is available; otherwise a short
independent session is opened (only valid for callers that manage their own
transaction, e.g. worker jobs).
"""

from sqlalchemy.orm import Session

from app.core.security import sanitize
from app.db.session import SessionLocal
from app.models.ops import AuditLog


def write_audit(
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
    db: Session | None = None,
) -> None:
    row = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=sanitize(metadata or {}),
    )
    if db is not None:
        db.add(row)
        db.commit()
        return
    try:
        session = SessionLocal()
        try:
            session.add(row)
            session.commit()
        finally:
            session.close()
    except Exception:  # noqa: BLE001 - audit failures shouldn't crash business flow, but log them
        import logging

        logging.getLogger(__name__).exception("failed to write audit log")
