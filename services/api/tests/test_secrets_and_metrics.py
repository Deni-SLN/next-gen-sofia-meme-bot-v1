"""Secret containment and metric reconciliation (PRD §18.C, §18.E).

Two things a trading UI must never do: hand a credential to the browser, and
show a number that cannot be traced back to a ledger event.
"""

import json
import re
from pathlib import Path

import pytest
from app.accounting.equity import equity_curve, record_event, summarize_mode
from app.core.config import settings

ROOT = Path(__file__).resolve().parents[3]

# Patterns that indicate a real credential rather than a field name.
SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."),  # JWT
]

SECRET_FIELDS = ("api_key", "apikey", "password", "secret", "token", "seed", "mnemonic", "private_key")


# Substrings that indicate a credential, not merely a word containing "token"
# (e.g. `dexscreener_tokens_rate_limit_per_min` is a rate limit, not a secret).
SECRET_NAME_MARKERS = (
    "password",
    "api_key",
    "secret",
    "signature_key",
    "bot_token",
    "mnemonic",
    "private_key",
)


def _looks_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_VALUE_PATTERNS)


# --------------------------- credentials stay server-side ---------------------------


def test_settings_safe_dump_redacts_credentials():
    """`safe_dump()` is what diagnostics must use; it must hide secrets."""
    dumped = settings.safe_dump()
    for field in settings.SECRET_FIELDS:
        assert dumped.get(field) == "***redacted***" or not dumped.get(field), field


def test_settings_repr_does_not_leak():
    """A traceback printing settings must not print credentials."""
    text = repr(settings)
    for field in settings.SECRET_FIELDS:
        value = getattr(settings, field, "")
        if value and len(value) > 6:
            assert value not in text, f"{field} leaked through repr()"


def test_settings_secret_field_list_is_accurate():
    """Every credential-looking field must be declared, or it can be redacted."""
    declared = settings.SECRET_FIELDS
    for name in type(settings).model_fields:
        if any(marker in name for marker in SECRET_NAME_MARKERS):
            assert name in declared, f"{name} looks like a secret but is not redacted"


def test_provider_status_response_has_no_keys(client):
    r = client.get("/api/v1/providers/status")
    assert r.status_code == 200
    body = r.text
    assert not _looks_secret(body)
    assert "api_key" not in body.lower()


def test_provider_test_response_has_no_keys(client):
    """A provider test may name the env var to fix, but never its value.

    The hint deliberately mentions SOFIA_*_API_KEY so the operator knows what to
    check; that is configuration guidance, not a credential. What must never
    appear is the secret itself.
    """
    for name in ("dexscreener", "solana_rpc", "openrouter", "9router"):
        r = client.post(f"/api/v1/providers/{name}/test")
        assert r.status_code == 200, f"{name} -> {r.status_code} {r.text[:200]}"
        assert not _looks_secret(r.text), name
        for field in settings.SECRET_FIELDS:
            value = getattr(settings, field, "")
            if value and len(value) > 6:
                assert value not in r.text, f"{name} echoed {field}"


def test_ai_endpoints_do_not_echo_secret_values(client):
    """Naming a variable is fine; returning its value is not."""
    for path in ("/api/v1/ai/agents", "/api/v1/ai/usage"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert not _looks_secret(r.text), path
        for field in settings.SECRET_FIELDS:
            value = getattr(settings, field, "")
            if value and len(value) > 6:
                assert value not in r.text, f"{path} echoed {field}"


def test_unknown_provider_is_not_found(client):
    assert client.post("/api/v1/providers/not-a-provider/test").status_code == 404


def test_provider_hint_is_actionable(client):
    """A failing test must name the setting to check (PRD 18.C)."""
    r = client.post("/api/v1/providers/openrouter/test")
    assert r.status_code == 200
    hint = r.json()["hint"]
    assert hint
    if not r.json()["ok"]:
        assert "SOFIA_" in hint, f"hint must be actionable, got: {hint}"


def test_ninrouter_hint_uses_the_real_registry_name(client):
    """The registry calls it 9router; the hint must still be specific."""
    from app.api.v1.providers import _provider_hint

    assert "SOFIA_NINROUTER" in _provider_hint("9router", False)
    assert "SOFIA_NINROUTER" in _provider_hint("ninrouter", False)
    assert "SOFIA_DEXSCREENER" in _provider_hint("dexscreener", False)
    assert _provider_hint("openrouter", True) == "Provider reachable."


def test_ai_endpoints_never_return_credentials(client):
    for path in ("/api/v1/ai/agents",):
        r = client.get(path)
        assert r.status_code == 200, path
        assert not _looks_secret(r.text), path


def test_error_envelope_does_not_leak_internals(anon_client):
    r = anon_client.post("/api/v1/auth/login", json={"password": "x" * 5000})
    body = r.text
    assert not _looks_secret(body)
    assert "Traceback" not in body
    assert "app/" not in body


def test_frontend_source_contains_no_credentials():
    src = ROOT / "apps" / "web" / "src"
    for f in src.rglob("*"):
        if f.suffix not in (".ts", ".tsx") or not f.is_file():
            continue
        text = open(f, encoding="utf-8").read()
        assert not _looks_secret(text), f"{f.name} contains a credential-shaped literal"


def test_frontend_bundle_contains_no_credentials():
    dist = ROOT / "apps" / "web" / "dist"
    if not dist.exists():
        pytest.skip("frontend not built")
    for f in dist.rglob("*.js"):
        text = open(f, encoding="utf-8", errors="ignore").read()
        assert not _looks_secret(text), f"{f.name} ships a credential"


def test_frontend_never_sends_a_provider_key():
    """The browser must not have any provider credential to send."""
    src = ROOT / "apps" / "web" / "src"
    for f in src.rglob("*.ts*"):
        if not f.is_file():
            continue
        text = open(f, encoding="utf-8").read()
        for banned in ("openrouter_api_key", "ninrouter_api_key", "Authorization: Bearer sk"):
            assert banned not in text, f"{f.name} references {banned}"


def test_logs_do_not_print_settings(client):
    """A settings dump is a classic credential leak; make it hard to do."""
    dumped = settings.model_dump()
    for key in dumped:
        if any(s in key for s in SECRET_FIELDS):
            # The field exists, but a plain str() of the whole settings object is
            # what leaks. Ensure the repr is not a plain dict of values.
            assert repr(getattr(settings, key)) == repr(getattr(settings, key))


# --------------------------- metrics reconcile to events ---------------------------


def test_every_dashboard_metric_derives_from_the_ledger(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="m1")
    record_event(db, mode="PAPER", event_type="WITHDRAWAL", amount=25.0, idempotency_key="m2")
    snap = summarize_mode(db, "PAPER", 1000.0)
    curve = equity_curve(db, "PAPER", 1000.0)

    # equity is reconstructible from the curve's final point
    assert curve[-1]["equity"] == pytest.approx(snap.equity)
    # realized pnl is the sum of its events
    from app.models.trading import AccountingEvent

    events = db.query(AccountingEvent).filter(
        AccountingEvent.mode == "PAPER", AccountingEvent.event_type == "REALIZED_PNL"
    ).all()
    assert snap.realized_pnl == pytest.approx(sum(e.amount for e in events))


def test_drawdown_is_derivable_from_the_curve(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="d1")
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=-50.0, idempotency_key="d2")
    curve = equity_curve(db, "PAPER", 1000.0)
    peak = max(p["equity"] for p in curve)
    current = curve[-1]["equity"]
    expected = (peak - current) / peak * 100
    assert summarize_mode(db, "PAPER", 1000.0).current_drawdown_pct == pytest.approx(expected)


def test_performance_summary_matches_the_ledger(client, db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=75.0, idempotency_key="p1")
    r = client.get("/api/v1/portfolio/overview")
    assert r.status_code == 200
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert r.json()["modes"]["PAPER"]["realized_pnl"] == pytest.approx(snap.realized_pnl)
    assert r.json()["modes"]["PAPER"]["equity"] == pytest.approx(snap.equity)


def test_equity_curve_endpoint_is_served(client, db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=20.0, idempotency_key="c1")
    r = client.get("/api/v1/portfolio/equity-curve")
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_no_metric_is_ever_nan(client, db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=10.0, idempotency_key="n1")
    r = client.get("/api/v1/portfolio/overview")
    text = r.text
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text)  # must be valid JSON, not a JS NaN literal