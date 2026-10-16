"""Authentication & authorization tests (PRD §3.3, §12 preamble, §16).

Covers: password hashing, persisted sessions with TTL/revocation, role
separation, and the requirement that every endpoint except health requires an
authenticated actor.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import (
    ROLE_OPERATOR,
    create_session,
    hash_password,
    purge_expired_sessions,
    resolve_session,
    revoke_session,
    sanitize,
    verify_password,
)
from app.main import create_app
from fastapi.routing import APIRoute

# Endpoints reachable without a bearer token. Health has no auth by contract;
# login must be reachable to obtain a token; logout is idempotent/best-effort.
PUBLIC_PATHS = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/logout"}
GUARD_NAMES = {"current_actor", "require_operator", "current_session"}


def _mounted_routes(app):
    """Yield (route, mounted_path) for every route in the app.

    An `APIRoute.path` already contains its own router's prefix, but not the
    prefix of the router it was included into, so the top-level mount prefix is
    derived from the app rather than hardcoded.
    """
    top = [
        r.original_router.prefix
        for r in app.router.routes
        if hasattr(r, "original_router") and getattr(r.original_router, "prefix", "")
    ]
    mount = top[0] if len(top) == 1 else ""

    def walk(router, acc):
        for r in getattr(router, "routes", []):
            if isinstance(r, APIRoute):
                yield r, acc + r.path
            elif hasattr(r, "original_router"):
                yield from walk(r.original_router, acc)

    return list(walk(app.router, mount))


def _routes():
    return _mounted_routes(create_app())


# ----------------------------- Password hashing -----------------------------


def test_password_hash_is_salted_and_verifiable():
    a = hash_password("correct horse battery staple")
    b = hash_password("correct horse battery staple")
    assert a != b, "each hash must use a fresh salt"
    assert a.startswith("pbkdf2_sha256$")


def test_hash_password_roundtrip(monkeypatch):
    encoded = hash_password("s3cret-pass")
    monkeypatch.setattr("app.core.security.settings.admin_password_hash", encoded)
    monkeypatch.setattr("app.core.security.settings.admin_password", "")
    assert verify_password("s3cret-pass") is True
    assert verify_password("wrong-pass") is False


def test_verify_password_rejects_malformed_hash(monkeypatch):
    monkeypatch.setattr("app.core.security.settings.admin_password_hash", "not-a-valid-hash")
    monkeypatch.setattr("app.core.security.settings.admin_password", "")
    assert verify_password("anything") is False


def test_verify_password_plaintext_fallback_is_constant_time(monkeypatch):
    monkeypatch.setattr("app.core.security.settings.admin_password_hash", "")
    monkeypatch.setattr("app.core.security.settings.admin_password", "plain-pass")
    assert verify_password("plain-pass") is True
    assert verify_password("plain-pass-x") is False


# ----------------------------- Sessions -----------------------------


def test_session_is_persisted_and_resolvable(db):
    token = create_session(db, actor="operator", role=ROLE_OPERATOR)
    assert len(token) > 20
    session = resolve_session(db, token)
    assert session is not None
    assert session.actor == "operator"
    assert session.role == ROLE_OPERATOR


def test_raw_token_is_never_stored(db):
    from app.models.system import AuthSession

    token = create_session(db, actor="operator")
    stored = db.query(AuthSession).all()
    assert len(stored) == 1
    assert token not in stored[0].token_hash
    assert len(stored[0].token_hash) == 64  # sha256 hex


def test_expired_session_is_rejected(db):
    token = create_session(db, actor="operator")
    from app.models.system import AuthSession

    row = db.query(AuthSession).first()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert resolve_session(db, token) is None


def test_revoked_session_is_rejected(db):
    token = create_session(db, actor="operator")
    assert revoke_session(db, token) is True
    assert resolve_session(db, token) is None
    assert revoke_session(db, token) is True  # idempotent


def test_unknown_token_is_rejected(db):
    assert resolve_session(db, "never-issued") is None


def test_purge_expired_sessions(db):
    from app.models.system import AuthSession

    create_session(db, actor="a")
    create_session(db, actor="b")
    row = db.query(AuthSession).first()
    row.expires_at = datetime.now(UTC) - timedelta(days=30)
    db.commit()
    assert purge_expired_sessions(db) >= 1


# ----------------------------- Route coverage -----------------------------


def test_every_endpoint_except_health_requires_auth():
    """PRD §12: 'Semua endpoint selain health check memerlukan auth'."""
    unprotected = []
    for r, path in _routes():
        if path in PUBLIC_PATHS:
            continue
        names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
        if not (names & GUARD_NAMES):
            unprotected.append(("+".join(sorted(r.methods - {"HEAD", "OPTIONS"})), path))
    assert not unprotected, f"endpoints reachable without credentials: {unprotected}"


def test_public_paths_are_exactly_the_agreed_ones():
    actual = {
        path
        for r, path in _routes()
        if not ({getattr(d.call, "__name__", "") for d in r.dependant.dependencies} & GUARD_NAMES)
    }
    assert actual == PUBLIC_PATHS


def test_write_endpoints_require_operator_role():
    """Observer must not be able to mutate state (PRD §3.2)."""
    require_operator_paths = set()
    for r, path in _routes():
        names = {getattr(d.call, "__name__", "") for d in r.dependant.dependencies}
        if "require_operator" in names:
            require_operator_paths.add(path)
    # Sensitive writes must be operator-gated.
    for path in (
        "/api/v1/bot/start",
        "/api/v1/bot/stop",
        "/api/v1/bot/emergency-stop",
        "/api/v1/risk/config",
        "/api/v1/wallet-policy",
        "/api/v1/profit-sweep/enable",
        "/api/v1/profit-sweep/disable",
        "/api/v1/wallet-transfers",
        # Paid-model approval must never be reachable by a read-only role
        # (PRD §9.4: explicit, per-model, operator-only consent).
        "/api/v1/ai/openrouter/approve-paid",
        "/api/v1/ai/agents/{agent_id}",
    ):
        assert path in require_operator_paths, f"{path} must require operator role"


# ----------------------------- Live requests -----------------------------


def test_read_endpoint_rejects_missing_token(anon_client):
    assert anon_client.get("/api/v1/tokens").status_code == 401


def test_read_endpoint_rejects_bogus_token(anon_client):
    r = anon_client.get("/api/v1/tokens", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401


def test_valid_token_grants_access(client):
    assert client.get("/api/v1/tokens").status_code == 200


def test_observer_can_read(observer_client):
    assert observer_client.get("/api/v1/tokens").status_code == 200


def test_observer_cannot_start_bot(observer_client):
    r = observer_client.post("/api/v1/bot/start", json={"mode": "PAPER"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_observer_cannot_touch_wallet_policy(observer_client):
    r = observer_client.put("/api/v1/wallet-policy", json={"sweep_percent": 10})
    assert r.status_code == 403


def test_observer_cannot_approve_paid_model(observer_client):
    """PRD 9.4: paid models require explicit operator consent."""
    r = observer_client.post("/api/v1/ai/openrouter/approve-paid", json={"model_id": "vendor/paid-model"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_login_rejects_bad_password(anon_client):
    r = anon_client.post("/api/v1/auth/login", json={"password": "nope"})
    assert r.status_code == 401


def test_logout_revokes_token(anon_client, db):
    token = create_session(db, actor="operator")
    headers = {"Authorization": "Bearer " + token}
    assert anon_client.get("/api/v1/tokens", headers=headers).status_code == 200
    assert anon_client.post("/api/v1/auth/logout", headers=headers).json() == {"ok": True}
    assert anon_client.get("/api/v1/tokens", headers=headers).status_code == 401


def test_health_needs_no_token(anon_client):
    assert anon_client.get("/api/v1/health").status_code == 200


# ----------------------------- Startup guards -----------------------------


def _startup(env, auth_disabled, live, password):
    import app.main as main_module
    from app.main import create_app
    from fastapi.testclient import TestClient

    monkey = pytest.MonkeyPatch()
    monkey.setattr(main_module.settings, "env", env)
    monkey.setattr(main_module.settings, "auth_disabled", auth_disabled)
    monkey.setattr(main_module.settings, "live_trading_enabled", live)
    monkey.setattr(main_module.settings, "admin_password", password)
    monkey.setattr(main_module.settings, "admin_password_hash", "")
    try:
        with TestClient(create_app()) as c:
            return "ok" if c.get("/api/v1/health").status_code == 200 else "bad-health"
    except RuntimeError as e:
        return str(e)
    finally:
        monkey.undo()


def test_startup_allows_production_with_auth_on():
    assert _startup("production", False, False, "pw") == "ok"


def test_startup_refuses_auth_disabled_in_production():
    msg = _startup("production", True, False, "pw")
    assert msg != "ok"
    assert "AUTH_DISABLED" in msg


def test_startup_allows_auth_disabled_in_development():
    assert _startup("development", True, False, "pw") == "ok"


def test_startup_refuses_live_trading_in_v1():
    """PRD 16: live trading is not a V1 capability."""
    msg = _startup("production", False, True, "pw")
    assert msg != "ok"
    assert "LIVE_TRADING_ENABLED" in msg


def test_startup_refuses_missing_credentials():
    msg = _startup("production", False, False, "")
    assert msg != "ok"
    assert "credential" in msg


# ----------------------------- Sanitizer -----------------------------


def test_sanitize_redacts_secrets():
    out = sanitize({"api_key": "sk-123", "nested": {"seed_phrase": "abc"}, "ok": 1})
    assert out["api_key"] == "***"
    assert out["nested"]["seed_phrase"] == "***"
    assert out["ok"] == 1


def test_sanitize_recurses_into_lists():
    out = sanitize([{"password": "p"}, {"safe": "v"}])
    assert out[0]["password"] == "***"
    assert out[1]["safe"] == "v"