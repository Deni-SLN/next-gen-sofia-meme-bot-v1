"""9Router provider via OpenAI-compatible API (FR §9.2).

Base URL configurable; defaults to https://9router.com/v1 or a local install.
Do not assume all 9Router models support tool calling, JSON schema, or
streaming — capabilities are validated/marked, not assumed.
"""

import time

import httpx

from app.core.config import settings
from app.core.errors import ForbiddenError, ProviderError
from app.providers.llm.base import BaseHTTPProvider, LLMRequest, LLMResponse


class NineRouterProvider(BaseHTTPProvider):
    name = "9router"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        super().__init__(
            (base_url or settings.ninrouter_base_url).rstrip("/"),
            api_key if api_key is not None else settings.ninrouter_api_key,
        )
        self.default_model = model or settings.ninrouter_model

    async def list_models(self) -> list[dict]:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except httpx.HTTPError as e:
            raise ProviderError(self.name, f"list_models failed: {e}") from e
        except Exception as e:  # noqa: BLE001
            # Any transport/decoding failure must surface as ProviderError so that
            # validate_model can fail closed instead of leaking the raw error.
            raise ProviderError(self.name, f"list_models failed: {e}") from e
        return [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                # 9Router does not publish uniform capabilities; mark unknown explicitly
                "capabilities_unknown": True,
            }
            for m in data
        ]

    async def validate_model(self, model_id: str) -> bool:
        if not model_id:
            return False
        try:
            models = await self.list_models()
            return any(m.get("id") == model_id for m in models)
        except ProviderError:
            # If we cannot verify, do not allow automatic routing to it (FR §9.4 principle)
            return False

    async def chat(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise ForbiddenError("9Router API key not configured")
        client = await self.get_client_safe()
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
        if resp.status_code >= 400:
            raise ProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        choices = data.get("choices") or [{}]
        usage = data.get("usage") or {}
        return LLMResponse(
            content=(choices[0].get("message") or {}).get("content", ""),
            actual_model=data.get("model") or request.model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=round(latency, 1),
            cost_usd=None,
            cost_status="UNKNOWN",
            request_id=data.get("id"),
            raw={"status_code": resp.status_code},
        )

    async def get_client_safe(self) -> httpx.AsyncClient:
        return await self._get_client()
