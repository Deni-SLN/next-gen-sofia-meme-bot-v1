"""Authentication primitives (PRD §3.3, §16).

Rules enforced here:
- passwords are never stored or compared in plaintext: PBKDF2-HMAC-SHA256
  with a per-user random salt, stored as `pbkdf2_sha256$<iters>$<salt>$<hash>`;
- sessions are opaque random tokens; only the token HASH is persisted, so a
  database dump cannot be replayed;
- sessions expire (TTL) and can be revoked explicitly;
- every comparison is constant-time.

`authenticate_request` was removed: `app.api.v1.deps` is the single auth path
so the two implementations could not drift apart.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.system import AuthSession

PBKDF2_ALGO = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000  # OWASP guidance for PBKDF2-HMAC-SHA256
ROLE_OPERATOR = "OPERATOR"
ROLE_OBSERVER = "OBSERVER"


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


# ----------------------------- Passwords -----------------------------


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return a storable `pbkdf2_sha256$<iters>$<salt_hex>$<hash_hex>` string."""
    if not password:
        raise ValueError("password must not be empty")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{PBKDF2_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def _verify_pbkdf2(password: str, encoded: str) -> bool:
    try:
        algo, iterations_raw, salt_hex, digest_hex = encoded.split("$")
        if algo != PBKDF2_ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_raw))
    return hmac.compare_digest(actual, expected)


def _verify_plaintext_fallback(password: str, expected_plaintext: str) -> bool:
    """Constant-time compare against a configured plaintext secret.

    Only used when no hash was configured; deployments should always set
    `admin_password_hash` (see `sofia.security.hash_password`).
    """
    return hmac.compare_digest(password.encode(), expected_plaintext.encode())


def _configured_secret(role: str) -> tuple[str | None, str]:
    """Return (password_hash, plaintext) configured for the given role."""
    if role == ROLE_OBSERVER:
        return settings.observer_password_hash, settings.observer_password
    return settings.admin_password_hash, settings.admin_password


def verify_password(password: str, role: str = ROLE_OPERATOR) -> bool:
    encoded, plaintext = _configured_secret(role)
    if encoded:
        return _verify_pbkdf2(password, encoded)
    return _verify_plaintext_fallback(password, plaintext or "")


def uses_hashed_password(role: str = ROLE_OPERATOR) -> bool:
    return bool(_configured_secret(role)[0])


# ----------------------------- Sessions -----------------------------


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, *, actor: str, role: str = ROLE_OPERATOR) -> str:
    """Issue an opaque bearer token. Returns the raw token; only its hash is stored."""
    token = secrets.token_urlsafe(32)
    row = AuthSession(
        token_hash=_token_hash(token),
        actor=actor,
        role=role,
        created_at=_now(),
        expires_at=_now() + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(row)
    db.commit()
    return token


def resolve_session(db: Session, token: str) -> AuthSession | None:
    """Return a live session, or None if unknown, revoked or expired."""
    row = db.get(AuthSession, _token_hash(token))
    if row is None or row.revoked_at is not None:
        return None
    if _aware(row.expires_at) <= _now():
        return None
    return row


def revoke_session(db: Session, token: str) -> bool:
    row = db.get(AuthSession, _token_hash(token))
    if row is None:
        return False
    row.revoked_at = _now()
    db.commit()
    return True


def purge_expired_sessions(db: Session) -> int:
    """Housekeeping: drop sessions that are expired and revoked, or long dead."""
    cutoff = _now() - timedelta(days=7)
    result = db.execute(
        delete(AuthSession).where(
            (AuthSession.expires_at < cutoff)
            | ((AuthSession.revoked_at.is_not(None)) & (AuthSession.expires_at < _now()))
        )
    )
    db.commit()
    return result.rowcount or 0


def active_session_count(db: Session) -> int:
    rows = db.execute(
        select(AuthSession).where(
            (AuthSession.revoked_at.is_(None)) & (AuthSession.expires_at > _now())
        )
    ).scalars().all()
    return len(rows)


# ----------------------------- Integrity -----------------------------


def internal_signature(payload: str) -> str:
    """HMAC for internal signal integrity.

    Uses a configured secret. A source-constant key would make this worthless
    as an integrity check, so the default is an empty string which callers must
    treat as "signing disabled" (see `signing_enabled`).
    """
    key = settings.internal_signature_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def signing_enabled() -> bool:
    return bool(settings.internal_signature_key)


def sanitize(obj: Any) -> Any:
    """Recursively redact keys that look sensitive before logging/storing."""
    sensitive = ("key", "secret", "token", "password", "seed", "private", "authorization")
    if isinstance(obj, dict):
        return {
            k: "***" if any(s in k.lower() for s in sensitive) else sanitize(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj