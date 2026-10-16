"""Error envelope tests (PRD §12.6).

Every error response must be:
    {"error": {"code", "message", "request_id", "details", "status"}}

`request_id` is required and must match the `X-Request-ID` response header.
"""

import pytest
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProviderError,
    UnauthorizedError,
    ValidationError,
    error_body,
    register_exception_handlers,
)
from app.main import create_app
from fastapi import APIRouter
from fastapi.testclient import TestClient


def _envelope(response):
    body = response.json()
    assert "error" in body, f"response has no 'error' envelope: {body}"
    return body["error"]


# ----------------------------- Envelope shape -----------------------------


def test_error_envelope_has_all_required_keys(client):
    r = client.get("/api/v1/nonexistent-route")
    assert r.status_code == 404
    err = _envelope(r)
    for key in ("code", "message", "request_id", "details", "status"):
        assert key in err, f"missing '{key}' in error envelope"


def test_application_error_carries_request_id(client):
    r = client.post("/api/v1/wallet-transfers", json={})
    assert r.status_code == 422
    err = _envelope(r)
    assert err["code"] == "VALIDATION_ERROR"
    assert err["request_id"]
    assert err["request_id"] != "None"


def test_request_id_matches_response_header(client):
    r = client.get("/api/v1/nonexistent-route")
    assert r.headers["X-Request-ID"] == _envelope(r)["request_id"]


def test_request_id_is_present_on_success_too(client):
    r = client.get("/api/v1/tokens")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")


def test_request_ids_are_unique_per_request(client):
    ids = {client.get("/api/v1/tokens").headers["X-Request-ID"] for _ in range(5)}
    assert len(ids) == 5


def test_supplied_request_id_is_echoed(client):
    r = client.get("/api/v1/nonexistent-route", headers={"X-Request-ID": "trace-abc-123"})
    assert r.status_code == 404
    assert r.headers["X-Request-ID"] == "trace-abc-123"
    assert _envelope(r)["request_id"] == "trace-abc-123"


def test_oversized_or_unsafe_request_id_is_replaced(client):
    """Do not echo arbitrary attacker-controlled text back."""
    nasty = "x" * 500 + "<script>"
    r = client.get("/api/v1/tokens", headers={"X-Request-ID": nasty})
    echoed = r.headers["X-Request-ID"]
    assert echoed != nasty
    assert "<" not in echoed and len(echoed) <= 64


# ----------------------------- Each error type -----------------------------


@pytest.mark.parametrize(
    "exc,expected_code,expected_status",
    [
        (NotFoundError("wallet", "abc"), "NOT_FOUND", 404),
        (ValidationError("bad input"), "VALIDATION_ERROR", 422),
        (UnauthorizedError(), "UNAUTHORIZED", 401),
        (ForbiddenError("nope"), "FORBIDDEN", 403),
        (ConflictError("duplicate"), "CONFLICT", 409),
        (ProviderError("dexscreener", "timeout"), "PROVIDER_ERROR", 502),
    ],
)
def test_each_error_type_renders_the_same_envelope(exc, expected_code, expected_status, db):
    from app.db.session import get_db

    probe = APIRouter()

    @probe.get("/_probe")
    def _raise():  # noqa: ANN202
        raise exc

    app = create_app()
    app.include_router(probe, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/_probe")
    assert r.status_code == expected_status
    err = _envelope(r)
    assert err["code"] == expected_code
    assert err["status"] == expected_status
    assert err["request_id"]
    assert isinstance(err["details"], dict)


# ----------------------------- Unhandled exceptions -----------------------------


def test_unhandled_exception_returns_500_envelope_not_a_crash(db):
    """The handler must catch a raw exception and still return a valid body."""
    from app.db.session import get_db

    probe = APIRouter()

    @probe.get("/_boom")
    def _boom():  # noqa: ANN202
        raise RuntimeError("internal detail: db password=hunter2")

    app = create_app()
    app.include_router(probe, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/_boom")
    assert r.status_code == 500
    err = _envelope(r)
    assert err["code"] == "INTERNAL_ERROR"
    assert err["request_id"]
    # The internal message must not leak.
    assert "hunter2" not in r.text
    assert "internal detail" not in r.text


def test_unhandled_handler_never_raises_itself(db):
    """Even a broken request object must still produce a response."""
    from app.db.session import get_db

    probe = APIRouter()

    @probe.get("/_boom2")
    def _boom2():  # noqa: ANN202
        raise ValueError("boom")

    app = create_app()
    app.include_router(probe, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/_boom2")
    assert r.status_code == 500
    assert _envelope(r)["code"] == "INTERNAL_ERROR"


# ----------------------------- Sanitisation -----------------------------


def test_validation_details_do_not_echo_the_submitted_input(client):
    """A rejected secret must not be reflected back in the error body."""
    r = client.post(
        "/api/v1/wallet-transfers",
        json={"api_key": "sk-super-secret", "amount_atomic": "not-a-number"},
    )
    assert r.status_code == 422
    assert "sk-super-secret" not in r.text


def test_error_details_are_sanitized():
    """`error_body` scrubs secret-looking keys before rendering."""
    class _Req:
        class state:  # noqa: N801
            request_id = "rid-1"

    body = error_body(_Req(), "CODE", "msg", {"api_key": "sk-1", "nested": {"token": "t"}, "ok": 2})
    details = body["error"]["details"]
    assert details["api_key"] == "***"
    assert details["nested"]["token"] == "***"
    assert details["ok"] == 2


def test_request_id_falls_back_when_middleware_did_not_run():
    class _Req:
        class state:  # noqa: N801
            pass

    body = error_body(_Req(), "CODE", "msg", {})
    assert body["error"]["request_id"] == "unknown"


# ----------------------------- Registration -----------------------------


def test_register_exception_handlers_is_idempotent(db):
    """Calling it twice must not duplicate or break handler wiring."""
    app = create_app()
    register_exception_handlers(app)
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        token = c.post("/api/v1/auth/login", json={"password": "test-password"})
        assert token.status_code == 200
        c.headers.update({"Authorization": "Bearer " + token.json()["token"]})
        r = c.get("/api/v1/tokens")
        assert r.status_code == 200
        assert r.headers.get("X-Request-ID")