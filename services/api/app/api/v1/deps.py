"""Authentication dependencies (PRD §3.3, §12 preamble).

Every endpoint except health requires an authenticated actor. Write endpoints
additionally require the operator role.
"""

from app.core.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import ROLE_OPERATOR, resolve_session
from app.db.session import get_db
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

BEARER_PREFIX = "Bearer "


def _bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith(BEARER_PREFIX):
        return None
    token = authorization[len(BEARER_PREFIX) :].strip()
    return token or None


def current_session(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Resolve the caller's session, or raise 401.

    When `auth_disabled` is on (local dev only, refused outside development)
    a synthetic dev operator is used.
    """
    if settings.auth_disabled:
        request.state.actor = "dev-operator"
        request.state.role = ROLE_OPERATOR
        return None
    token = _bearer(authorization)
    if token is None:
        raise UnauthorizedError("Missing bearer token")
    session = resolve_session(db, token)
    if session is None:
        raise UnauthorizedError("Invalid or expired session")
    request.state.actor = session.actor
    request.state.role = session.role
    return session


def current_actor(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> str:
    """Actor identity for audit + auth. Required on every non-health endpoint."""
    session = current_session(request, db, authorization)
    return "dev-operator" if session is None else session.actor


def require_operator(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> str:
    """Write endpoints: the caller must hold the operator role (PRD §3.2)."""
    session = current_session(request, db, authorization)
    if session is None:  # auth_disabled dev bypass
        return "dev-operator"
    if session.role != ROLE_OPERATOR:
        raise ForbiddenError(f"role {session.role} may not perform this action")
    return session.actor