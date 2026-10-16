"""System & auth endpoints (FR section 12.1)."""

from datetime import UTC, datetime

from app.api.v1.deps import BEARER_PREFIX, current_actor, require_operator
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    ROLE_OBSERVER,
    ROLE_OPERATOR,
    create_session,
    purge_expired_sessions,
    revoke_session,
    verify_password,
)
from app.db.session import get_db
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["system"])


class LoginRequest(BaseModel):
    password: str
    role: str = ROLE_OPERATOR


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": settings.app_name, "version": settings.engine_version}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    from app.models.analysis import AnalysisRun, Signal
    from app.models.trading import OrderIntent, Position
    from app.services.bot_service import get_bot_state

    state = get_bot_state(db)
    return {
        "app": settings.app_name,
        "engine_version": settings.engine_version,
        "scoring_config_version": settings.scoring_config_version,
        "risk_rule_version": settings.risk_rule_version,
        "live_trading_enabled": settings.live_trading_enabled,
        "auth_disabled": settings.auth_disabled,
        "bot": state,
        "counts": {
            "analysis_runs": db.query(AnalysisRun).count(),
            "signals": db.query(Signal).count(),
            "orders": db.query(OrderIntent).count(),
            "positions": db.query(Position).count(),
        },
        "server_time": datetime.now(UTC).isoformat(),
    }


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Password login. Issues an opaque bearer token persisted with a TTL."""
    role = payload.role if payload.role in (ROLE_OPERATOR, ROLE_OBSERVER) else ROLE_OPERATOR
    # Observer login is refused when no observer secret is configured at all.
    if role == ROLE_OBSERVER and not (
        settings.observer_password_hash or settings.observer_password
    ):
        raise UnauthorizedError("Observer access is not configured")
    if not verify_password(payload.password, role):
        raise UnauthorizedError("Invalid credentials")
    actor = "operator" if role == ROLE_OPERATOR else "observer"
    token = create_session(db, actor=actor, role=role)
    from app.services.audit_service import write_audit

    write_audit(actor, "auth_login", "auth_session", None, {"role": role}, db=db)
    return {
        "token": token,
        "token_type": "bearer",
        "actor": actor,
        "role": role,
        "expires_in_seconds": settings.session_ttl_seconds,
    }


@router.get("/system/audit-logs")
def audit_logs(
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    """Recent audit entries (FR §16). Sanitized at write time."""
    from app.models.ops import AuditLog

    q = db.query(AuditLog)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(min(limit, 500)).all()
    return {
        "items": [
            {
                "id": r.id,
                "actor": r.actor,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "metadata": r.metadata_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/auth/logout")
def logout(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith(BEARER_PREFIX):
        token = authorization[len(BEARER_PREFIX) :].strip()
        if revoke_session(db, token):
            from app.services.audit_service import write_audit

            write_audit("operator", "auth_logout", "auth_session", None, {}, db=db)
    return {"ok": True}


@router.post("/auth/sessions/purge")
def purge_sessions(db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Housekeeping: drop dead sessions. Operator-only."""
    return {"purged": purge_expired_sessions(db)}
