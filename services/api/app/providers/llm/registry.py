"""Provider registry + agent orchestration helpers (FR §9.5-§9.7).

Agents never call providers directly; everything flows through this registry
so usage, cost, and the actual model used are always recorded.
"""

import asyncio
import json

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.llm.base import LLMProvider, LLMRequest
from app.providers.llm.ninrouter import NineRouterProvider
from app.providers.llm.openrouter import OpenRouterProvider
from app.providers.llm.schemas import validate as validate_schema

log = get_logger(__name__)

_providers: dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    if name not in _providers:
        if name == "openrouter":
            _providers[name] = OpenRouterProvider()
        elif name == "9router":
            _providers[name] = NineRouterProvider()
        else:
            raise ValueError(f"unknown provider: {name}")
    return _providers[name]


def reset_providers() -> None:
    _providers.clear()


def get_default_provider_name() -> str:
    if settings.openrouter_api_key:
        return "openrouter"
    if settings.ninrouter_api_key:
        return "9router"
    return "openrouter"


DEFAULT_AGENTS = [
    {"agent_name": "technical-analysis", "provider": None, "model_id": None},
    {"agent_name": "onchain-risk", "provider": None, "model_id": None},
    {"agent_name": "market-research", "provider": None, "model_id": None},
    {"agent_name": "signal-validation", "provider": None, "model_id": None},
    {"agent_name": "strategy-research", "provider": None, "model_id": None},
]


def _candidates(db, agent_name: str) -> list[tuple[str, str]]:
    """Resolve the (provider, model) candidates for an agent, in order.

    Without fallback enabled this is exactly one candidate: the configured
    provider/model (or that provider's own default). With fallback enabled the
    configured provider stays first and the configured order supplies the rest.

    The model follows the *provider*, not the other way round. An earlier
    version handed every candidate `settings.openrouter_default_model`, so an
    agent configured for 9Router with no explicit model asked 9Router for
    `openrouter/free` - a router id that only exists on OpenRouter.
    """
    from app.models.system import AgentConfig

    cfg = db.query(AgentConfig).filter(AgentConfig.agent_name == agent_name).first()
    provider_name = (cfg.provider if cfg and cfg.provider else None) or get_default_provider_name()
    model_id = (cfg.model_id if cfg and cfg.model_id else None) or _default_model_for(provider_name)

    primary = (provider_name, model_id)
    if not settings.llm_cross_provider_fallback:
        return [primary]

    out = [primary]
    for name in settings.provider_fallback_order:
        if name == provider_name:
            continue
        # A fallback provider gets ITS OWN default model. Reusing the primary's
        # model id across providers is how a 9Router fallback ended up asking
        # for `openrouter/free`, a router id that does not exist there. An
        # explicitly configured model_id applies to the primary only, and a
        # fallback can therefore never be handed a paid model implicitly.
        out.append((name, _default_model_for(name)))
    return out


def _default_model_for(provider_name: str) -> str:
    """The default model for a provider, from that provider's own settings."""
    if provider_name == "9router":
        return settings.ninrouter_model or settings.openrouter_default_model
    return settings.openrouter_default_model


async def run_agent(
    db,
    agent_name: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 1024,
    schema: dict | None = None,
    validate_model: bool = True,
) -> dict:
    """Run an agent chat, persist an llm_request usage row, return parsed JSON.

    Three things this now does that it previously did not:

    * **Validates the model before every request.** `validate_model` was
      implemented on both providers and called from nowhere, so an approved-model
      check existed without ever running.
    * **Validates the output.** Malformed structured output is recorded as
      `INVALID` with the violations attached, and returned as a failure - not as
      a silent `parsed: None` that reads downstream as "nothing to say".
    * **Records the fallback chain.** Every candidate attempt gets its own
      `llm_request` row, so which provider actually answered is reconstructable.
    """
    from app.models.ops import LlmRequest
    from app.models.system import AgentConfig
    from app.providers.llm.base import is_free_model

    candidates = _candidates(db, agent_name)

    cfg = db.query(AgentConfig).filter(AgentConfig.agent_name == agent_name).first()
    max_out = min(max_tokens, cfg.max_output_tokens if cfg else max_tokens)
    timeout = cfg.timeout_seconds if cfg and cfg.timeout_seconds else settings.llm_timeout_seconds

    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]

    attempts: list[dict] = []
    last_error: str | None = None

    for provider_name, model_id in candidates:
        provider = get_provider(provider_name)
        req = LLMRequest(model=model_id, messages=messages, max_tokens=max_out)

        row = LlmRequest(
            agent_name=agent_name, provider=provider_name, requested_model=model_id, status="PENDING"
        )
        db.add(row)
        db.commit()

        # --- model gate ---
        if validate_model:
            try:
                allowed = await asyncio.wait_for(provider.validate_model(model_id), timeout=timeout)
            except Exception as e:  # noqa: BLE001 - unverifiable is not allowed
                row.status = "MODEL_UNVERIFIED"
                row.error_metadata = {"error": f"validate_model raised: {e}"[:500]}
                db.commit()
                attempts.append({"provider": provider_name, "model": model_id, "outcome": "MODEL_UNVERIFIED"})
                last_error = f"model {model_id} could not be verified on {provider_name}"
                continue
            if not allowed:
                row.status = "MODEL_REJECTED"
                row.error_metadata = {"error": "model not allowed by provider policy"[:500]}
                db.commit()
                attempts.append({"provider": provider_name, "model": model_id, "outcome": "MODEL_REJECTED"})
                last_error = f"model {model_id} rejected by {provider_name} policy"
                log.warning("agent %s: %s refused model %s", agent_name, provider_name, model_id)
                continue

        # --- request ---
        try:
            resp = await asyncio.wait_for(provider.chat(req), timeout=timeout)
        except Exception as e:  # noqa: BLE001 - AI failure must never break the pipeline
            row.status = "ERROR"
            row.error_metadata = {"error": str(e)[:500]}
            db.commit()
            attempts.append({"provider": provider_name, "model": model_id, "outcome": "ERROR",
                             "error": str(e)[:200]})
            log.warning("agent %s failed on %s: %s", agent_name, provider_name, e)
            last_error = str(e)
            continue

        row.status = "OK"
        row.actual_model = resp.actual_model
        row.latency_ms = resp.latency_ms
        row.prompt_tokens = resp.prompt_tokens
        row.completion_tokens = resp.completion_tokens
        row.total_tokens = resp.total_tokens
        row.cost_usd = resp.cost_usd
        row.cost_status = resp.cost_status
        row.request_id = resp.request_id
        db.commit()

        # --- output ---
        parsed, parse_error = _parse_output(resp.content)
        if parse_error is not None:
            row.status = "INVALID_OUTPUT"
            row.error_metadata = {"error": parse_error[:500]}
            db.commit()
            attempts.append({"provider": provider_name, "model": model_id, "outcome": "INVALID_OUTPUT"})
            return {
                "ok": False,
                "agent": agent_name,
                "provider": provider_name,
                "requested_model": model_id,
                "actual_model": resp.actual_model,
                "error": parse_error,
                "content": resp.content,
                "attempts": attempts,
            }

        violations: list[str] = []
        if schema is not None:
            violations = validate_schema(parsed, schema)
        if violations:
            row.status = "INVALID_OUTPUT"
            row.error_metadata = {"violations": violations[:20]}
            db.commit()
            attempts.append({"provider": provider_name, "model": model_id, "outcome": "SCHEMA_VIOLATION"})
            log.warning("agent %s returned invalid structured output: %s", agent_name, violations[:5])
            return {
                "ok": False,
                "agent": agent_name,
                "provider": provider_name,
                "requested_model": model_id,
                "actual_model": resp.actual_model,
                "error": "structured output failed schema validation",
                "violations": violations,
                "content": resp.content,
                "attempts": attempts,
            }

        attempts.append({"provider": provider_name, "model": model_id, "outcome": "OK"})
        return {
            "ok": True,
            "agent": agent_name,
            "provider": provider_name,
            "requested_model": model_id,
            "actual_model": resp.actual_model,
            "content": resp.content,
            "parsed": parsed,
            "attempts": attempts,
            "usage": {
                "total_tokens": resp.total_tokens,
                "latency_ms": resp.latency_ms,
                "cost_usd": resp.cost_usd,
                "cost_status": resp.cost_status,
                "is_free": is_free_model(resp.actual_model),
            },
        }

    return {
        "ok": False,
        "agent": agent_name,
        "error": last_error or "no provider available",
        "attempts": attempts,
    }


def _parse_output(content: str) -> tuple[object | None, str | None]:
    """Parse structured output, distinguishing 'not JSON' from 'JSON that is
    not an object'.

    `None` is a legitimate result for an agent asked for prose. Anything the
    caller asked to be structured has to be an object, otherwise the schema
    pass would be validating `None` against `{"type": "object"}` and reporting a
    confusing violation instead of "the model did not return JSON".
    """

    text = (content or "").strip()
    if not text:
        return None, "empty response"
    if not text.startswith("{") and not text.startswith("["):
        # Prose is fine; the caller's schema decides whether that is enough.
        return None, None
    try:
        return json.loads(text), None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"response was not valid JSON: {e}"
