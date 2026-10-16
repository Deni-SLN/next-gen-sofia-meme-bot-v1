"""Provider & AI agent endpoints (FR §12.1, §9).

All LLM calls go through the backend registry. OpenRouter free-first policy is
enforced server-side; paid models require explicit per-model approval.
"""

import asyncio
from datetime import UTC

from app.api.v1.deps import current_actor, require_operator
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.ops import LlmRequest
from app.models.system import AgentConfig
from app.providers.llm.registry import DEFAULT_AGENTS, get_provider
from app.services.audit_service import write_audit
from app.services.provider_service import record_provider_health
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

log = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])
providers_router = APIRouter(tags=["providers"])


def _run_async(coro):
    return asyncio.run(coro)


# ----------------------------- Providers -----------------------------


@providers_router.get("/providers/status")
def providers_status(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    from app.models.market import ProviderHealth

    rows = db.query(ProviderHealth).all()
    return {
        "providers": [
            {
                "provider": r.provider,
                "status": r.status,
                "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
                "last_error_at": r.last_error_at.isoformat() if r.last_error_at else None,
                "last_error_message": r.last_error_message,
                "error_count": r.error_count,
                "latency_ms": r.latency_ms,
            }
            for r in rows
        ]
    }


@providers_router.post("/providers/{provider}/test")
def test_provider(
    provider: str,
    db: Session = Depends(get_db),
    actor: str = Depends(current_actor),
):
    """Actionable connection test. Records health; never leaks secrets.

    Covers both provider families: the LLM providers and the market/on-chain
    providers reported by /providers/status. An operator who sees a provider
    listed as degraded must be able to test exactly that one.
    """
    health = _health_check(provider)
    if health is None:
        raise NotFoundError("provider", provider)
    result = health
    record_provider_health(
        provider,
        ok=result.get("ok", False),
        latency_ms=result.get("latency_ms"),
        error=result.get("detail"),
    )
    write_audit(actor, "provider_test", "provider", provider, {"ok": result.get("ok")}, db)
    return {
        "provider": provider,
        "ok": bool(result.get("ok")),
        "status_code": result.get("status_code"),
        "latency_ms": result.get("latency_ms"),
        "detail": result.get("detail"),
        "hint": _provider_hint(provider, bool(result.get("ok"))),
    }


def _health_check(provider: str) -> dict | None:
    """Run a health check for any known provider, or None if unknown."""
    try:
        prov = get_provider(provider)
    except ValueError:
        market = _market_health_check(provider)
        return market
    return _run_async(prov.health_check())


def _market_health_check(provider: str) -> dict | None:
    """Health check for market/on-chain providers."""
    import time

    if provider == "dexscreener":
        from app.providers.market.dexscreener import DexScreenerProvider

        probe = DexScreenerProvider()

        async def _check():
            start = time.perf_counter()
            try:
                await probe.trending(limit=1)
                await probe.close()
            except Exception as e:  # noqa: BLE001 - a health check never raises
                return {
                    "provider": provider,
                    "ok": False,
                    "status_code": None,
                    "latency_ms": None,
                    "detail": str(e)[:200],
                }
            return {
                "provider": provider,
                "ok": True,
                "status_code": 200,
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "detail": "reachable",
            }

        return _run_async(_check())

    if provider == "solana_rpc":
        from app.providers.onchain.solana_rpc import SolanaRPCProvider

        rpc = SolanaRPCProvider()
        result = _run_async(rpc.health_check())
        return result if isinstance(result, dict) else None

    return None


# Env var names must match core/config.py, otherwise the hint sends the operator
# looking for a variable that does not exist.
_PROVIDER_HINTS: dict[str, str] = {
    "openrouter": "Check SOFIA_OPENROUTER_API_KEY and network access to openrouter.ai.",
    # The registry names this provider "9router"; keep "ninrouter" as an alias so
    # either spelling produces the actionable hint.
    "9router": (
        "Check SOFIA_NINROUTER_API_KEY, SOFIA_NINROUTER_BASE_URL and SOFIA_NINROUTER_MODEL "
        "(9Router OpenAI-compatible endpoint)."
    ),
    "ninrouter": (
        "Check SOFIA_NINROUTER_API_KEY, SOFIA_NINROUTER_BASE_URL and SOFIA_NINROUTER_MODEL "
        "(9Router OpenAI-compatible endpoint)."
    ),
    "dexscreener": (
        "Check SOFIA_DEXSCREENER_BASE_URL and outbound network access to api.dexscreener.com."
    ),
    "solana_rpc": "Check SOFIA_SOLANA_RPC_URL and outbound network access to the Solana RPC.",
}


def _provider_hint(provider: str, ok: bool) -> str:
    if ok:
        return "Provider reachable."
    return _PROVIDER_HINTS.get(provider, "Verify provider configuration and network access.")



# ----------------------------- AI agents -----------------------------


def _agent_json(r: AgentConfig) -> dict:
    return {
        "id": r.id,
        "agent_name": r.agent_name,
        "provider": r.provider,
        "model_id": r.model_id,
        "routing_mode": r.routing_mode,
        "capabilities": r.capabilities,
        "timeout_seconds": r.timeout_seconds,
        "max_retries": r.max_retries,
        "max_output_tokens": r.max_output_tokens,
        "context_budget": r.context_budget,
        "fallback_policy": r.fallback_policy,
        "enabled": bool(r.enabled),
        "version": r.version,
    }


@router.post("/agents/{agent_name}/run")
def run_single_agent(
    agent_name: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    """Run one registered agent on a signal or a token, on demand.

    Narrative only. The result is returned to the caller and, for a signal,
    attached to its analysis run's `ai_summary` - which scoring, the risk
    assessor and the risk gate never read. There is no path from here to an
    order, a position, or the ledger.
    """
    from app.models.analysis import Signal
    from app.models.market import Token, TokenPair
    from app.services.agent_service import (
        AGENT_SPECS,
        research_strategy,
        run_narrative_agents,
        validate_signal,
    )

    spec = AGENT_SPECS.get(agent_name)
    if spec is None:
        raise ValidationError(f"unknown agent {agent_name}; known: {sorted(AGENT_SPECS)}")

    body = payload or {}
    signal_id = body.get("signal_id")
    if signal_id:
        signal = db.get(Signal, signal_id)
        if signal is None:
            raise NotFoundError("signal", signal_id)
        return {"agent": agent_name, "result": validate_signal(db, signal)}

    mint = body.get("mint")
    if not mint:
        raise ValidationError("mint or signal_id required")
    token = db.query(Token).filter(Token.mint_address == mint).first()
    if token is None:
        raise NotFoundError("token", mint)
    pair = (
        db.query(TokenPair)
        .filter(TokenPair.token_id == token.id)
        .order_by(TokenPair.created_at.desc())
        .first()
    )

    if agent_name == "strategy-research":
        parsed, meta = research_strategy(db, token, pair)
        return {"agent": agent_name, "result": parsed, "meta": meta}

    if agent_name in ("technical-analysis", "market-research", "onchain-risk"):
        payload_out = run_narrative_agents(db, token, pair, agents=(agent_name,))
        return {"agent": agent_name, "result": payload_out, "spec_purpose": spec.purpose}

    raise ValidationError(f"agent {agent_name} has no on-demand entry point")


@router.get("/agents")
def list_agents(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    """Return configured agents, seeding defaults on first call (no code change needed)."""
    rows = db.query(AgentConfig).order_by(AgentConfig.agent_name).all()
    if not rows:
        for a in DEFAULT_AGENTS:
            db.add(AgentConfig(agent_name=a["agent_name"]))
        db.commit()
        rows = db.query(AgentConfig).order_by(AgentConfig.agent_name).all()

    from app.services.agent_service import AGENT_SPECS

    registered = [a["agent_name"] for a in DEFAULT_AGENTS]
    return {
        "agents": [_agent_json(r) for r in rows],
        # A registered agent with no spec and no call site is a name, not a
        # feature. Surfaced so the gap is visible instead of implied.
        "unimplemented_agents": sorted(set(registered) - set(AGENT_SPECS)),
    }


@router.put("/agents/{agent_id}")
def update_agent(
    agent_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    agent = db.get(AgentConfig, agent_id)
    if agent is None:
        raise NotFoundError("agent", agent_id)
    allowed = {
        "provider",
        "model_id",
        "routing_mode",
        "capabilities",
        "timeout_seconds",
        "max_retries",
        "max_output_tokens",
        "context_budget",
        "fallback_policy",
        "enabled",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ValidationError(f"unknown fields: {sorted(unknown)}", {"allowed": sorted(allowed)})
    for k, v in payload.items():
        setattr(agent, k, v)
    try:
        agent.version = f"v{int(agent.version.lstrip('v')) + 1}"
    except (ValueError, AttributeError):
        agent.version = "v2"
    db.commit()
    write_audit(actor, "update_agent", "agent_config", agent_id, {"fields": sorted(payload)}, db)
    return _agent_json(agent)


# ----------------------------- Usage / requests -----------------------------


@router.get("/usage")
def ai_usage(
    db: Session = Depends(get_db),
    days: int = Query(30, le=365),
    actor: str = Depends(current_actor),
):
    from datetime import datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.query(LlmRequest).filter(LlmRequest.created_at >= since).all()
    total_tokens = sum(r.total_tokens or 0 for r in rows)
    cost_known = sum(r.cost_usd for r in rows if r.cost_usd is not None)
    by_provider: dict[str, dict] = {}
    for r in rows:
        b = by_provider.setdefault(r.provider, {"requests": 0, "tokens": 0, "errors": 0})
        b["requests"] += 1
        b["tokens"] += r.total_tokens or 0
        if r.status == "ERROR":
            b["errors"] += 1
    return {
        "window_days": days,
        "requests": len(rows),
        "total_tokens": total_tokens,
        "cost_usd_known": round(cost_known, 6),
        "cost_status": "KNOWN/ESTIMATED where available; UNKNOWN otherwise (never fabricated as 0)",
        "by_provider": by_provider,
        "idr_estimate": round(cost_known * 16300.0, 2),
    }


@router.get("/requests")
def ai_requests(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
    offset: int = 0,
    status: str | None = None,
    actor: str = Depends(current_actor),
):
    q = db.query(LlmRequest)
    if status:
        q = q.filter(LlmRequest.status == status)
    total = q.count()
    rows = q.order_by(LlmRequest.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "agent_name": r.agent_name,
                "provider": r.provider,
                "requested_model": r.requested_model,
                "actual_model": r.actual_model,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "retry_count": r.retry_count,
                "total_tokens": r.total_tokens,
                "cost_usd": r.cost_usd,
                "cost_status": r.cost_status,
                "request_id": r.request_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/openrouter/approve-paid")
def approve_paid_model(payload: dict, actor: str = Depends(require_operator)):
    from app.providers.llm.openrouter import approve_paid_model as _approve

    model_id = (payload or {}).get("model_id")
    if not model_id:
        raise ValidationError("model_id required")
    _approve(model_id, actor)
    return {"ok": True, "approved": model_id, "note": "Per-model approval recorded; not a global grant."}


@providers_router.get("/providers/{provider}/models")
def list_provider_models(provider: str, actor: str = Depends(current_actor)):
    from app.providers.llm.openrouter import is_free_model

    try:
        prov = get_provider(provider)
    except ValueError as e:
        raise NotFoundError("provider", provider) from e
    models = _run_async(prov.list_models())
    if provider == "openrouter":
        for m in models:
            m["free"] = bool(m.get("is_free")) or is_free_model(m.get("id") or "")
    return {"provider": provider, "models": models}
