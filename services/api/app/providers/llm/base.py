"""LLM provider abstraction (FR §9.5) with OpenRouter free-first enforcement (FR §9.4).

Backend validates models before sending requests. Paid models require manual
selection + explicit per-model confirmation; automatic routing never selects
a paid model silently.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

OPENROUTER_DEFAULT_MODEL = "openrouter/free"


def is_free_model(model_id: str) -> bool:
    """OpenRouter free heuristic: router model or ':free' suffix."""
    if not model_id:
        return False
    if model_id == OPENROUTER_DEFAULT_MODEL:
        return True
    return model_id.endswith(":free")


@dataclass
class LLMRequest:
    model: str
    messages: list[dict[str, str]]
    max_tokens: int = 1024
    temperature: float = 0.2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str
    actual_model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: float
    cost_usd: float | None
    cost_status: str  # KNOWN | ESTIMATED | UNKNOWN
    request_id: str | None
    raw: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str

    async def list_models(self) -> list[dict]: ...
    async def validate_model(self, model_id: str) -> bool: ...
    async def chat(self, request: LLMRequest) -> LLMResponse: ...
    async def health_check(self) -> dict: ...


class BaseHTTPProvider:
    name = "base"

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> dict:
        start = time.perf_counter()
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            latency = (time.perf_counter() - start) * 1000
            ok = resp.status_code < 400
            return {
                "provider": self.name,
                "ok": ok,
                "status_code": resp.status_code,
                "latency_ms": round(latency, 1),
                "detail": "reachable" if ok else resp.text[:200],
            }
        except Exception as e:  # noqa: BLE001 - health must never raise
            return {
                "provider": self.name,
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "detail": str(e)[:200],
            }
