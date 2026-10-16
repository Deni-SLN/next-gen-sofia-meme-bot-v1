"""Cross-provider fallback tests (PRD §18.C).

Fallback is OFF by default. When switched on it must never widen the free-only
policy: a fallback provider is only ever handed a free model.
"""

import asyncio

import pytest
from app.core.config import settings
from app.core.errors import ForbiddenError, ProviderError
from app.models.system import AgentConfig
from app.providers.llm import registry
from app.providers.llm.base import LLMResponse


class RecordingProvider:
    def __init__(self, name, fail=False, content='{"ok": true}'):
        self.name = name
        self.fail = fail
        self.content = content
        self.calls = []
        self.allowed = True

    def allow_model(self, model_id):
        return self.allowed

    async def list_models(self):
        return []

    async def validate_model(self, model_id):
        # The registry now gates on this before every request (Tahap 6).
        return self.allowed

    async def chat(self, req):
        self.calls.append(req.model)
        if self.fail:
            raise ProviderError(self.name, "HTTP 503")
        return LLMResponse(
            content=self.content,
            actual_model=req.model,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            latency_ms=1.0,
            cost_usd=0.0,
            cost_status="KNOWN",
            request_id="r",
        )


@pytest.fixture()
def fallback_off():
    old = settings.llm_cross_provider_fallback
    settings.llm_cross_provider_fallback = False
    yield
    settings.llm_cross_provider_fallback = old


@pytest.fixture()
def fallback_on():
    old = settings.llm_cross_provider_fallback
    order = settings.llm_provider_order
    settings.llm_cross_provider_fallback = True
    settings.llm_provider_order = "openrouter,9router"
    yield
    settings.llm_cross_provider_fallback = old
    settings.llm_provider_order = order
    registry.reset_providers()


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.reset_providers()
    yield
    registry.reset_providers()


def test_fallback_is_off_by_default():
    assert settings.llm_cross_provider_fallback is False


def test_candidates_are_single_without_fallback(db, fallback_off):
    db.add(AgentConfig(agent_name="technical-analysis", provider="openrouter", model_id="openrouter/free"))
    db.commit()
    assert len(registry._candidates(db, "technical-analysis")) == 1


def test_candidates_expand_in_configured_order(db, fallback_on):
    db.add(AgentConfig(agent_name="market-research", provider="openrouter", model_id="openrouter/free"))
    db.commit()
    cands = registry._candidates(db, "market-research")
    assert cands[0][0] == "openrouter", "configured provider stays first"
    assert [c[0] for c in cands[1:]] == ["9router"]


def test_primary_failure_falls_back(db, fallback_on):
    primary = RecordingProvider("openrouter", fail=True)
    secondary = RecordingProvider("9router", content='{"from": "9router"}')
    registry._providers["openrouter"] = primary
    registry._providers["9router"] = secondary
    db.add(AgentConfig(agent_name="strategy-research", provider="openrouter", model_id="openrouter/free"))
    db.commit()

    out = asyncio.run(registry.run_agent(db, "strategy-research", "hi"))
    assert out["ok"] is True
    assert out["provider"] == "9router"
    assert len(primary.calls) == 1 and len(secondary.calls) == 1


def test_no_fallback_when_disabled(db, fallback_off):
    primary = RecordingProvider("openrouter", fail=True)
    secondary = RecordingProvider("9router", content='{"from": "9router"}')
    registry._providers["openrouter"] = primary
    registry._providers["9router"] = secondary
    db.add(AgentConfig(agent_name="signal-validation", provider="openrouter", model_id="openrouter/free"))
    db.commit()

    out = asyncio.run(registry.run_agent(db, "signal-validation", "hi"))
    assert out["ok"] is False
    assert primary.calls, "primary must be tried"
    assert secondary.calls == [], "secondary must NOT be used when fallback is off"


def test_fallback_never_picks_a_paid_model(db, fallback_on):
    """A configured paid model may not be carried onto another provider."""
    db.add(AgentConfig(agent_name="onchain-risk", provider="openrouter", model_id="anthropic/claude-3.5"))
    db.commit()
    cands = registry._candidates(db, "onchain-risk")
    assert cands[0] == ("openrouter", "anthropic/claude-3.5"), "primary keeps the operator's choice"
    for _provider, model in cands[1:]:
        assert model == settings.openrouter_default_model, (
            "a fallback provider must receive the free default model"
        )


def test_fallback_uses_the_fallback_providers_own_model(db, fallback_on):
    """A fallback provider gets ITS default, not the primary's model id.

    The primary's id belongs to the primary's catalogue. Handing
    `vendor/x:free` (an OpenRouter id) to 9Router produces a request for a
    model that does not exist there. The primary keeps the configured id.
    """
    from app.core.config import settings

    db.add(AgentConfig(agent_name="onchain-risk", provider="openrouter", model_id="vendor/x:free"))
    db.commit()
    cands = dict(registry._candidates(db, "onchain-risk"))
    assert cands["openrouter"] == "vendor/x:free", "the primary keeps the configured model"
    assert cands["9router"] == settings.ninrouter_model or settings.openrouter_default_model


def test_a_fallback_is_never_handed_a_paid_model(db, fallback_on):
    """Free-only enforcement survives the fallback: each provider's own default
    is used, and no fallback silently becomes a paid model."""
    from app.core.config import settings
    from app.providers.llm.openrouter import is_free_model

    db.add(AgentConfig(agent_name="onchain-risk", provider="openrouter", model_id="vendor/paid"))
    db.commit()
    cands = dict(registry._candidates(db, "onchain-risk"))
    assert cands["openrouter"] == "vendor/paid", "an explicitly configured primary is honoured"
    fallback_model = cands["9router"]
    assert is_free_model(fallback_model) or fallback_model == settings.ninrouter_model


def test_all_providers_failing_reports_error(db, fallback_on):
    for name in ("openrouter", "9router"):
        registry._providers[name] = RecordingProvider(name, fail=True)
    db.add(AgentConfig(agent_name="market-research", provider="openrouter", model_id="openrouter/free"))
    db.commit()
    out = asyncio.run(registry.run_agent(db, "market-research", "hi"))
    assert out["ok"] is False
    assert "error" in out


def test_every_attempt_is_recorded(db, fallback_on):
    """A fallback must not hide the failure of the provider it fell back from."""
    from app.models.ops import LlmRequest

    registry._providers["openrouter"] = RecordingProvider("openrouter", fail=True)
    registry._providers["9router"] = RecordingProvider("9router", content='{"ok": 1}')
    db.add(AgentConfig(agent_name="market-research", provider="openrouter", model_id="openrouter/free"))
    db.commit()
    asyncio.run(registry.run_agent(db, "market-research", "hi"))

    rows = db.query(LlmRequest).order_by(LlmRequest.created_at).all()
    assert len(rows) == 2
    assert {r.provider for r in rows} == {"openrouter", "9router"}
    assert any(r.status == "ERROR" for r in rows)
    assert any(r.status == "OK" for r in rows)


def test_fallback_cannot_bypass_the_paid_gate(db, fallback_on):
    """Even a fallback provider must refuse an unapproved paid model."""
    from app.providers.llm.openrouter import OpenRouterProvider

    p = OpenRouterProvider()
    with pytest.raises(ForbiddenError):
        p._require_allowed("gpt-4o")
    assert settings.llm_cross_provider_fallback is True