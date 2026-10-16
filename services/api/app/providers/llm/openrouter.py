"""OpenRouter provider (FR §9.3, §9.4). Free-first is enforced backend-side."""

import time

import httpx

from app.core.config import settings
from app.core.errors import ForbiddenError, ProviderError
from app.core.logging import get_logger
from app.providers.llm.base import (
    BaseHTTPProvider,
    LLMRequest,
    LLMResponse,
    is_free_model,
)

log = get_logger(__name__)


def _parse_price(value) -> float | None:
    """Parse a price string. Returns None when absent or unparseable.

    None means "unknown" and must never be coerced to 0.0: a zero price would
    mark the model free (FR §9.4 free-first enforcement).
    """
    if value is None or value == "":
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price == price and price not in (float("inf"), float("-inf")) else None


def load_approved_paid_models() -> set[str]:
    """Approved paid models stored per provider/model (not a global silent grant)."""
    from app.services.provider_service import get_setting

    return set(get_setting("openrouter_approved_paid_models", []))


def approve_paid_model(model_id: str, actor: str) -> None:
    from app.services.provider_service import get_setting, set_setting

    approved = set(get_setting("openrouter_approved_paid_models", []))
    approved.add(model_id)
    set_setting("openrouter_approved_paid_models", sorted(approved))
    from app.services.audit_service import write_audit

    # This helper is session-independent (it goes through get_setting/set_setting),
    # so the audit row is written on its own session.
    write_audit(actor, "approve_paid_model", "provider", "openrouter", {"model_id": model_id})


class OpenRouterProvider(BaseHTTPProvider):
    name = "openrouter"

    def __init__(self) -> None:
        super().__init__(
            settings.openrouter_base_url,
            settings.openrouter_api_key,
        )
        self._models_cache: list[dict] | None = None

    async def list_models(self) -> list[dict]:
        if self._models_cache is not None:
            return self._models_cache
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"list_models failed: {e}") from e
        out = []
        for m in data:
            pricing = m.get("pricing") or {}
            # Missing/unparseable pricing is UNKNOWN, not free. Defaulting it to 0
            # would classify an unpriced (possibly paid) model as free and create an
            # automatic route to a paid model (FR §9.4).
            prompt_price = _parse_price(pricing.get("prompt"))
            free = is_free_model(m.get("id", "")) or (
                prompt_price is not None and prompt_price == 0.0
            )
            out.append(
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "context_length": m.get("context_length"),
                    "pricing_prompt": pricing.get("prompt"),
                    "is_free": free,
                }
            )
        self._models_cache = out
        return out

    async def validate_model(self, model_id: str) -> bool:
        """Backend gate: free models always allowed; paid only if explicitly approved."""
        if is_free_model(model_id):
            return True
        if model_id in load_approved_paid_models():
            return True
        return False

    def _require_allowed(self, model_id: str) -> None:
        if not model_id:
            raise ForbiddenError("model id required")
        if is_free_model(model_id):
            return
        if model_id in load_approved_paid_models():
            return
        raise ForbiddenError(
            "Paid OpenRouter model requires explicit manual selection and confirmation",
            details={"model_id": model_id, "hint": "confirm via POST /ai/openrouter/approve-paid"},
        )

    async def chat(self, request: LLMRequest) -> LLMResponse:
        # Backend enforcement — UI confirmation alone is not enough (FR §9.4)
        self._require_allowed(request.model)
        client = await self._get_client()
        start = time.perf_counter()
        try:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": request.model,
                    "messages": request.messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"chat failed: {e}") from e
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code in (401, 402, 403):
            raise ProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:200]}")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ProviderError(self.name, f"HTTP {resp.status_code}: rate limit or server error")
        if resp.status_code >= 400:
            raise ProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        choices = data.get("choices") or [{}]
        usage = data.get("usage") or {}
        actual_model = data.get("model") or request.model
        cost = None
        cost_status = "UNKNOWN"
        # openrouter/free and :free models are $0
        if is_free_model(actual_model):
            cost, cost_status = 0.0, "KNOWN"
        if actual_model != request.model:
            log.info(
                "openrouter actual model differs: requested=%s actual=%s",
                request.model,
                actual_model,
            )
        return LLMResponse(
            content=(choices[0].get("message") or {}).get("content", ""),
            actual_model=actual_model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=round(latency, 1),
            cost_usd=cost,
            cost_status=cost_status,
            request_id=data.get("id"),
            raw={"status_code": resp.status_code},
        )
