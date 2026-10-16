"""DEX Screener market data adapter (FR §10.1).

Handles: discovery/search/token endpoints, rate limiting, request cache +
in-flight dedup, retry/backoff for 429/5xx, normalization, freshness.
Missing values stay None (never coerced to zero).
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger

log = get_logger(__name__)


class SchemaChangeError(ProviderError):
    """The provider response no longer matches the shape the pipeline needs.

    Raised instead of silently returning None, so a renamed field becomes a
    visible provider-health event rather than a quiet stream of missing data
    (PRD §10.4).
    """

    def __init__(self, message: str) -> None:
        super().__init__("dexscreener", "schema change: " + message, {"kind": "schema_change"})


@dataclass
class NormalizedPair:
    chain: str
    mint_address: str
    pair_address: str
    symbol: str | None
    name: str | None
    dex_id: str | None
    price_usd: float | None
    liquidity_usd: float | None
    volume_5m: float | None
    volume_1h: float | None
    volume_24h: float | None
    buys_5m: int | None
    sells_5m: int | None
    buys_1h: int | None
    sells_1h: int | None
    price_change_5m: float | None
    price_change_1h: float | None
    price_change_24h: float | None
    fdv: float | None
    market_cap: float | None
    pair_created_at: datetime | None
    observed_at: datetime
    source: str = "dexscreener"
    raw_hash: str | None = None
    # Token decimals from the provider's baseToken block, when present.
    decimals: int | None = None
    quote_token_address: str | None = None


def _f(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _i(v) -> int | None:
    f = _f(v)
    return int(f) if f is not None else None


def _dt(v) -> datetime | None:
    if not v:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=UTC)
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        return None


class DexScreenerProvider:
    name = "dexscreener"

    # Per-endpoint rate limits (PRD §10.1). Endpoints are not assumed to share
    # a single quota, so each gets its own budget.
    ENDPOINT_LIMITS: dict[str, int] = {
        "search": settings.dexscreener_search_rate_limit_per_min,
        "tokens": settings.dexscreener_tokens_rate_limit_per_min,
        "default": settings.dexscreener_rate_limit_per_min,
    }

    def __init__(self, base_url: str | None = None, rate_per_min: int | None = None) -> None:
        self.base_url = (base_url or settings.dexscreener_base_url).rstrip("/")
        self.rate_per_min = rate_per_min or settings.dexscreener_rate_limit_per_min
        self._min_interval = 60.0 / max(1, self.rate_per_min)
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, object]] = {}
        self._inflight: dict[str, asyncio.Future] = {}
        self._client: httpx.AsyncClient | None = None
        # One throttle clock per endpoint, so a burst on /search cannot spend
        # the /tokens budget.
        self._last_call: dict[str, float] = {}

    def _interval_for(self, endpoint: str) -> float:
        per_min = self.ENDPOINT_LIMITS.get(endpoint) or self.ENDPOINT_LIMITS["default"]
        return 60.0 / max(1, per_min)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=httpx.Timeout(10.0), limits=httpx.Limits(max_connections=10)
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _throttle(self, endpoint: str) -> None:
        interval = self._interval_for(endpoint)
        async with self._lock:
            now = time.monotonic()
            wait = self._last_call.get(endpoint, 0.0) + interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[endpoint] = time.monotonic()

    async def _request(
        self, path: str, params: dict | None = None, ttl: float | None = None, endpoint: str = "default"
    ) -> dict:
        key = f"{path}?{sorted((params or {}).items())}"
        ttl = ttl if ttl is not None else settings.market_cache_ttl_seconds
        cached = self._cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]  # type: ignore[return-value]
        if key in self._inflight:
            return await self._inflight[key]
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._inflight[key] = fut
        try:
            result = await self._fetch_with_retry(path, params, endpoint)
            self._cache[key] = (time.monotonic() + ttl, result)
            fut.set_result(result)
            return result
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            self._inflight.pop(key, None)

    async def _fetch_with_retry(
        self, path: str, params: dict | None, endpoint: str = "default", max_retries: int = 3
    ) -> dict:
        client = await self._get_client()
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            await self._throttle(endpoint)
            start = time.perf_counter()
            try:
                resp = await client.get(path, params=params)
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code == 429 or resp.status_code >= 500:
                    retry_after = float(resp.headers.get("retry-after", 0) or 0)
                    from app.services.provider_service import record_provider_health

                    record_provider_health(self.name, ok=False, error=f"HTTP {resp.status_code}")
                    last_exc = ProviderError(self.name, f"HTTP {resp.status_code}", {"path": path})
                    if attempt < max_retries:
                        delay = retry_after or (0.5 * (2**attempt)) + 0.1 * attempt
                        await asyncio.sleep(delay)
                        continue
                    raise last_exc
                resp.raise_for_status()
                try:
                    data = resp.json()
                except ValueError as e:
                    from app.services.provider_service import record_provider_health

                    record_provider_health(self.name, ok=False, error="malformed JSON")
                    raise ProviderError(self.name, "malformed JSON", {"path": path}) from e
                from app.services.provider_service import record_provider_health

                record_provider_health(self.name, latency_ms=latency, ok=True)
                return data
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
        from app.services.provider_service import record_provider_health

        record_provider_health(self.name, ok=False, error=str(last_exc))
        raise ProviderError(self.name, f"request failed after retries: {last_exc}", {"path": path})

    # ---- Public API ----

    async def search(self, query: str, limit: int = 20) -> list[NormalizedPair]:
        data = await self._request(
            "/latest/dex/search", {"q": query}, endpoint="search"
        )
        pairs = data.get("pairs") or []
        out: list[NormalizedPair] = []
        for x in pairs[: limit * 2]:
            p = self._safe_normalize(x)
            if p:
                out.append(p)
        return out[:limit]

    async def token_pairs(self, mint: str, chain: str = "solana") -> list[NormalizedPair]:
        data = await self._request(f"/latest/dex/tokens/{mint}", endpoint="tokens")
        pairs = data.get("pairs") or []
        out: list[NormalizedPair] = []
        for x in pairs:
            p = self._safe_normalize(x)
            if p and p.chain == chain:
                out.append(p)
        return out

    async def trending(self, limit: int = 20) -> list[NormalizedPair]:
        data = await self._request("/latest/dex/search", {"q": "SOL"}, endpoint="search")
        pairs = data.get("pairs") or []
        out: list[NormalizedPair] = []
        for x in pairs:
            p = self._safe_normalize(x)
            if p and p.chain == "solana":
                out.append(p)
        out.sort(key=lambda p: p.liquidity_usd or 0, reverse=True)
        return out[:limit]

    def _safe_normalize(self, x) -> NormalizedPair | None:
        """Normalize one entry, skipping (but reporting) a malformed record.

        One bad row must not discard the whole provider response, but a schema
        change must still be visible in provider health.
        """
        try:
            return self._normalize(x)
        except SchemaChangeError as e:
            from app.services.provider_service import record_provider_health

            log.warning("%s schema change: %s", self.name, e)
            record_provider_health(self.name, ok=False, error=f"schema change: {e}")
            return None

    def _normalize(self, x: dict) -> NormalizedPair | None:
        if not isinstance(x, dict):
            raise SchemaChangeError(f"expected an object, got {type(x).__name__}")
        chain = x.get("chainId")
        base = x.get("baseToken") or {}
        mint = base.get("address")
        pair_addr = x.get("pairAddress")
        if chain != "solana" or not mint or not pair_addr:
            # Not a Solana pair we can use, but the payload itself was fine.
            return None
        liq = x.get("liquidity") or {}
        txns = x.get("txns") or {}
        m5 = txns.get("m5") or {}
        h1 = txns.get("h1") or {}
        pct = x.get("priceChange") or {}
        quote = x.get("quoteToken") or {}
        raw = str(x)
        self._check_schema(x)
        return NormalizedPair(
            chain=chain,
            mint_address=mint,
            pair_address=pair_addr,
            symbol=base.get("symbol"),
            name=base.get("name"),
            dex_id=x.get("dexId"),
            price_usd=_f(x.get("priceUsd")),
            liquidity_usd=_f(liq.get("usd")),
            volume_5m=_f((x.get("volume") or {}).get("m5")),
            volume_1h=_f((x.get("volume") or {}).get("h1")),
            volume_24h=_f((x.get("volume") or {}).get("h24")),
            buys_5m=_i(m5.get("buys")),
            sells_5m=_i(m5.get("sells")),
            buys_1h=_i(h1.get("buys")),
            sells_1h=_i(h1.get("sells")),
            price_change_5m=_f(pct.get("m5")),
            price_change_1h=_f(pct.get("h1")),
            price_change_24h=_f(pct.get("h24")),
            fdv=_f(x.get("fdv")),
            market_cap=_f(x.get("marketCap")),
            pair_created_at=_dt(x.get("pairCreatedAt")),
            decimals=_i(base.get("decimals")),
            quote_token_address=quote.get("address"),
            observed_at=datetime.now(UTC),
            raw_hash=hashlib.sha256(raw.encode()).hexdigest()[:32],
        )

    # Keys the pipeline actually depends on. If the provider renames or drops
    # one of these, that is a schema change and must surface loudly rather than
    # silently yielding None (PRD §10.4).
    REQUIRED_PAIR_KEYS = (
        "chainId",
        "pairAddress",
        "baseToken",
        "priceUsd",
        "liquidity",
        "volume",
        "txns",
        "priceChange",
    )

    def _check_schema(self, x: dict) -> None:
        missing = [k for k in self.REQUIRED_PAIR_KEYS if k not in x]
        if missing:
            raise SchemaChangeError(
                f"DEX Screener pair payload is missing required keys: {missing}"
            )

