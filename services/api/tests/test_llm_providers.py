"""AI provider tests (Phase 4 exit gate: FR §9.2-§9.5).

The gate this file defends: there is NO automatic path to a paid OpenRouter
model. A model is free only when the provider explicitly says so. Anything
unreadable fails closed.
"""

import asyncio

import pytest
from app.core.errors import ForbiddenError, ProviderError
from app.providers.llm.base import OPENROUTER_DEFAULT_MODEL, LLMRequest, is_free_model
from app.providers.llm.ninrouter import NineRouterProvider
from app.providers.llm.openrouter import (
    OpenRouterProvider,
    _parse_price,
    approve_paid_model,
)

# ----------------------------- Free-model identification -----------------------------


@pytest.mark.parametrize(
    "model_id",
    ["openrouter/free", "meta-llama/llama-3.1-8b:free", "vendor/thing:free"],
)
def test_free_model_ids_are_free(model_id):
    assert is_free_model(model_id) is True


@pytest.mark.parametrize("model_id", ["gpt-4o", "anthropic/claude-3.5", "vendor/thing"])
def test_paid_model_ids_are_not_free(model_id):
    assert is_free_model(model_id) is False


def test_empty_model_id_is_not_free():
    assert is_free_model("") is False


# ----------------------------- Price parsing -----------------------------


def test_parse_price_reads_numeric_strings():
    assert _parse_price("0") == 0.0
    assert _parse_price("0.000003") == pytest.approx(3e-6)
    assert _parse_price(0) == 0.0


@pytest.mark.parametrize("value", [None, "", "not-a-number", "NaN", "inf", "-inf"])
def test_parse_price_returns_none_when_unknown(value):
    assert _parse_price(value) is None


# ----------------------------- list_models classification -----------------------------


def _models_response(models):
    class R:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": models}

    return R()


def _provider_with_models(models):
    p = OpenRouterProvider()

    class FakeClient:
        async def get(self, *a, **k):
            return _models_response(models)

    async def _client():
        return FakeClient()

    p._get_client = _client
    return p


def test_model_with_zero_pricing_is_free():
    p = _provider_with_models(
        [{"id": "vendor/zero", "pricing": {"prompt": "0"}}]
    )
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is True


def test_model_with_paid_pricing_is_not_free():
    p = _provider_with_models([{"id": "vendor/paid", "pricing": {"prompt": "0.000003"}}])
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is False


def test_model_with_missing_pricing_is_not_free():
    """Unknown pricing must never be read as free (would open a paid route)."""
    p = _provider_with_models([{"id": "vendor/unpriced"}])
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is False


def test_model_with_unparseable_pricing_is_not_free():
    p = _provider_with_models([{"id": "vendor/weird", "pricing": {"prompt": "lots"}}])
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is False


def test_free_suffix_wins_over_paid_pricing():
    p = _provider_with_models([{"id": "vendor/x:free", "pricing": {"prompt": "0.01"}}])
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is True


def test_empty_pricing_block_is_not_free():
    p = _provider_with_models([{"id": "vendor/empty", "pricing": {}}])
    out = asyncio.run(p.list_models())
    assert out[0]["is_free"] is False


# ----------------------------- Backend enforcement -----------------------------


@pytest.fixture(autouse=True)
def _isolated_approvals(monkeypatch):
    """Keep paid-model approvals off the real database.

    `load_approved_paid_models`/`approve_paid_model` go through get_setting/
    set_setting, which open their own SessionLocal session. In tests that would
    write to the developer's actual database, so approvals are stubbed here.
    """
    approved: set[str] = set()

    monkeypatch.setattr(
        "app.providers.llm.openrouter.load_approved_paid_models", lambda: set(approved)
    )

    from app.services import provider_service

    def _set(key, value):
        approved.clear()
        approved.update(value or [])

    def _get(key, default=None):
        return set(approved) if approved else default

    monkeypatch.setattr(provider_service, "set_setting", _set)
    monkeypatch.setattr(provider_service, "get_setting", _get)
    monkeypatch.setattr(
        "app.services.audit_service.write_audit", lambda *a, **k: None, raising=False
    )
    return approved


def test_paid_model_is_rejected_without_approval(db):
    p = OpenRouterProvider()
    with pytest.raises(ForbiddenError):
        p._require_allowed("anthropic/claude-3.5")


def test_free_model_is_allowed_without_approval():
    p = OpenRouterProvider()
    p._require_allowed(OPENROUTER_DEFAULT_MODEL)
    p._require_allowed("vendor/x:free")


def test_missing_model_id_is_rejected():
    p = OpenRouterProvider()
    with pytest.raises(ForbiddenError):
        p._require_allowed("")


def test_paid_model_allowed_after_explicit_approval(db):
    """Approval is per-model and must be recorded, not granted globally."""
    from app.providers.llm import openrouter as or_mod

    model_id = "anthropic/claude-3.5"
    assert model_id not in or_mod.load_approved_paid_models()
    approve_paid_model(model_id, actor="operator")
    assert model_id in or_mod.load_approved_paid_models()
    p = OpenRouterProvider()
    p._require_allowed(model_id)  # now permitted


def test_approval_does_not_leak_to_other_models(db):
    """Approving one paid model must not authorise a different one."""
    from app.providers.llm import openrouter as or_mod

    approve_paid_model("approved/model", actor="operator")
    assert "approved/model" in or_mod.load_approved_paid_models()
    p = OpenRouterProvider()
    with pytest.raises(ForbiddenError):
        p._require_allowed("other/paid-model")


def test_validate_model_fails_closed_for_paid(db):
    p = OpenRouterProvider()
    assert asyncio.run(p.validate_model("unapproved-paid-model")) is False
    assert asyncio.run(p.validate_model("openrouter/free")) is True


def test_chat_refuses_paid_model_before_any_network_call(db):
    """The gate must run before the HTTP call, not after it."""
    called = {"n": 0}

    class Boom:
        async def post(self, *a, **k):
            called["n"] += 1
            raise AssertionError("network must not be reached")

    async def _client():
        return Boom()

    p = OpenRouterProvider()
    p._get_client = _client
    with pytest.raises(ForbiddenError):
        asyncio.run(p.chat(LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "x"}])))
    assert called["n"] == 0


# ----------------------------- Chat cost accounting -----------------------------


def _chat_response(status=200, model="openrouter/free", text="hi"):
    class R:
        def __init__(self):
            self.status_code = status
            self.text = text

        def json(self):
            return {
                "id": "req-1",
                "model": model,
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    return R()


def test_free_response_cost_is_known_zero():
    p = OpenRouterProvider()

    class FakeClient:
        async def post(self, *a, **k):
            return _chat_response()

    async def _client():
        return FakeClient()

    p._get_client = _client
    resp = asyncio.run(p.chat(LLMRequest(model="openrouter/free", messages=[])))
    assert resp.cost_usd == 0.0
    assert resp.cost_status == "KNOWN"


def test_silent_model_upgrade_is_surfaced():
    """If the provider returns a different model, it is reported, not hidden."""
    p = OpenRouterProvider()

    class FakeClient:
        async def post(self, *a, **k):
            return _chat_response(model="anthropic/claude-3.5")

    async def _client():
        return FakeClient()

    p._get_client = _client
    resp = asyncio.run(p.chat(LLMRequest(model="openrouter/free", messages=[])))
    assert resp.actual_model == "anthropic/claude-3.5"
    # Upgraded to a non-free model -> cost must not be claimed as zero.
    assert resp.cost_status == "UNKNOWN"
    assert resp.cost_usd is None


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 503])
def test_chat_maps_error_statuses_to_provider_error(status):
    p = OpenRouterProvider()

    class FakeClient:
        async def post(self, *a, **k):
            r = _chat_response()
            r.status_code = status
            r.text = "err"
            return r

    async def _client():
        return FakeClient()

    p._get_client = _client
    with pytest.raises(ProviderError):
        asyncio.run(p.chat(LLMRequest(model="openrouter/free", messages=[])))


# ----------------------------- 9Router -----------------------------


def test_9router_requires_api_key():
    p = NineRouterProvider(api_key="")
    with pytest.raises(ForbiddenError):
        asyncio.run(p.chat(LLMRequest(model="anything", messages=[])))


def test_9router_validate_model_fails_closed_on_error():
    class BadClient:
        async def get(self, *a, **k):
            raise RuntimeError("network down")

    async def _client():
        return BadClient()

    p = NineRouterProvider(api_key="k")
    p._get_client = _client
    # Cannot verify -> must not be auto-routable (FR §9.4 principle)
    assert asyncio.run(p.validate_model("some-model")) is False


def test_9router_marks_capabilities_unknown():
    class R:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "m1", "name": "M1"}]}

    class FakeClient:
        async def get(self, *a, **k):
            return R()

    async def _client():
        return FakeClient()

    p = NineRouterProvider(api_key="k")
    p._get_client = _client
    out = asyncio.run(p.list_models())
    assert out[0]["capabilities_unknown"] is True


# ----------------------------- Structured output -----------------------------


def test_malformed_structured_output_is_not_a_pipeline_failure(db):
    """A model returning prose instead of JSON must not break analysis."""
    from app.providers.llm import registry

    class Prose:
        name = "prose"

        async def validate_model(self, model_id):
            # The registry now gates on this before every request (Tahap 6).
            return True

        async def chat(self, req):
            from app.providers.llm.base import LLMResponse

            return LLMResponse(
                content="Sure! Here is my opinion: the token looks great.",
                actual_model="openrouter/free",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                latency_ms=1.0,
                cost_usd=0.0,
                cost_status="KNOWN",
                request_id="r",
            )

    registry._providers["prose"] = Prose()
    from app.core.config import settings

    old = settings.openrouter_api_key
    settings.openrouter_api_key = ""
    try:
        from app.models.system import AgentConfig

        db.add(AgentConfig(agent_name="market-research", provider="prose", model_id="openrouter/free"))
        db.commit()
        out = asyncio.run(registry.run_agent(db, "market-research", "give me json"))
    finally:
        settings.openrouter_api_key = old
        registry.reset_providers()

    assert out["ok"] is True
    assert out["parsed"] is None, "unparseable output must be surfaced as None, not faked"
    assert "opinion" in out["content"], "the raw text is still returned to the caller"


def test_valid_structured_output_is_parsed(db):
    from app.providers.llm import registry

    class Json:
        name = "json"

        async def validate_model(self, model_id):
            # The registry now gates on this before every request (Tahap 6).
            return True

        async def chat(self, req):
            from app.providers.llm.base import LLMResponse

            return LLMResponse(
                content='{"verdict": "reject", "confidence": 0.9}',
                actual_model="openrouter/free",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                latency_ms=1.0,
                cost_usd=0.0,
                cost_status="KNOWN",
                request_id="r",
            )

    registry._providers["jsonp"] = Json()
    from app.core.config import settings

    old = settings.openrouter_api_key
    settings.openrouter_api_key = ""
    try:
        from app.models.system import AgentConfig

        db.add(AgentConfig(agent_name="signal-validation", provider="jsonp", model_id="openrouter/free"))
        db.commit()
        out = asyncio.run(registry.run_agent(db, "signal-validation", "json please"))
    finally:
        settings.openrouter_api_key = old
        registry.reset_providers()

    assert out["parsed"] == {"verdict": "reject", "confidence": 0.9}


# ----------------------------- Registry -----------------------------


def test_registry_rejects_unknown_provider():
    from app.providers.llm.registry import get_provider

    with pytest.raises(ValueError):
        get_provider("does-not-exist")


def test_agent_failure_is_recorded_and_never_raises(db):
    """An AI outage must not break the deterministic pipeline."""
    from app.models.ops import LlmRequest
    from app.providers.llm import registry

    class Broken:
        name = "broken"

        async def validate_model(self, model_id):
            # The registry now gates on this before every request (Tahap 6).
            return True

        async def chat(self, req):
            raise ProviderError("broken", "HTTP 500")

    registry._providers["broken"] = Broken()
    from app.core.config import settings

    old = settings.openrouter_api_key
    settings.openrouter_api_key = ""
    try:
        from app.models.system import AgentConfig

        db.add(AgentConfig(agent_name="technical-analysis", provider="broken", model_id="m"))
        db.commit()
        out = asyncio.run(registry.run_agent(db, "technical-analysis", "hello"))
    finally:
        settings.openrouter_api_key = old
        registry.reset_providers()

    assert out["ok"] is False
    row = db.query(LlmRequest).order_by(LlmRequest.created_at.desc()).first()
    assert row is not None and row.status == "ERROR"


def test_agent_success_records_usage(db):
    from app.models.ops import LlmRequest
    from app.models.system import AgentConfig
    from app.providers.llm import registry

    class Ok:
        name = "ok"

        async def validate_model(self, model_id):
            # The registry now gates on this before every request (Tahap 6).
            return True

        async def chat(self, req):
            from app.providers.llm.base import LLMResponse

            return LLMResponse(
                content='{"verdict": "ok"}',
                actual_model="openrouter/free",
                prompt_tokens=5,
                completion_tokens=5,
                total_tokens=10,
                latency_ms=1.0,
                cost_usd=0.0,
                cost_status="KNOWN",
                request_id="r1",
            )

    registry._providers["okp"] = Ok()
    db.add(AgentConfig(agent_name="market-research", provider="okp", model_id="openrouter/free"))
    db.commit()
    out = asyncio.run(registry.run_agent(db, "market-research", "hi"))
    registry.reset_providers()

    assert out["ok"] is True
    assert out["parsed"] == {"verdict": "ok"}
    assert out["usage"]["is_free"] is True
    row = db.query(LlmRequest).order_by(LlmRequest.created_at.desc()).first()
    assert row.status == "OK" and row.cost_status == "KNOWN"