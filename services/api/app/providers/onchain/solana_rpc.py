"""Solana RPC adapter (FR §10.2) for on-chain reads.

Supports mint/freeze authority and token supply checks. Endpoint is
configurable; public RPC intended for prototype volumes only.
"""

import asyncio
import time

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger

log = get_logger(__name__)


class SolanaRPCProvider:
    name = "solana_rpc"

    def __init__(self, url: str | None = None) -> None:
        self.url = url or settings.solana_rpc_url
        self._min_interval = 60.0 / max(1, settings.solana_rpc_rate_limit_per_min)
        self._last_call = 0.0
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._req_id = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_sol_balance_lamports(self, owner: str, commitment: str = "confirmed") -> int:
        """SOL balance of `owner`, in lamports.

        Raises rather than returning 0 on an unreadable balance: a caller that
        treats an error as a zero balance would let a sweep move funds that may
        not be there. `None` would be the other wrong answer; the exception is
        what forces the caller to record UNKNOWN.
        """
        result = await self._call(
            "getBalance",
            [owner, {"commitment": commitment}],
            max_retries=1,
        )
        value = result.get("value")
        if not isinstance(value, dict):
            raise ProviderError(self.name, "getBalance returned no value", {"owner": owner})
        lamports = value.get("lamports")
        if not isinstance(lamports, int) or lamports < 0:
            raise ProviderError(
                self.name, "getBalance returned an unusable lamport count", {"owner": owner}
            )
        return lamports

    async def get_token_balance_atomic(
        self, owner: str, mint: str, commitment: str = "confirmed"
    ) -> int:
        """SPL token balance of `owner` for `mint`, in atomic units.

        An account with no token account legitimately holds zero. That is read
        from the provider's own empty result, not inferred from a failure -
        an RPC error still raises.
        """
        result = await self._call(
            "getTokenAccountsByOwner",
            [
                owner,
                {"mint": mint},
                {"commitment": commitment, "encoding": "jsonParsed"},
            ],
            max_retries=1,
        )
        accounts = result.get("value")
        if not isinstance(accounts, list):
            raise ProviderError(
                self.name, "getTokenAccountsByOwner returned no account list", {"owner": owner}
            )
        total = 0
        for account in accounts:
            info = (account or {}).get("account", {}).get("data", {}).get("parsed", {})
            amount = (
                info.get("info", {})
                .get("tokenAmount", {})
                .get("amount")
            )
            if amount is None:
                continue
            try:
                total += int(amount)
            except (TypeError, ValueError) as exc:
                raise ProviderError(
                    self.name, "token amount was not an integer", {"owner": owner, "mint": mint}
                ) from exc
        return total

    async def get_signature_statuses(
        self, signature: str, commitment: str = "confirmed"
    ) -> list[dict]:
        """Confirmation status for a signature, or an empty list if unknown."""
        result = await self._call(
            "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}]
        )
        value = result.get("value")
        if value is None:
            return []
        if not isinstance(value, list):
            raise ProviderError(self.name, "getSignatureStatuses returned an unexpected shape")
        return [v for v in value if isinstance(v, dict)]

    async def health_check(self) -> dict:
        """Cheapest RPC round trip that proves the endpoint is usable.

        Never raises: a health check reports failure, it does not propagate it.
        `getHealth` is side-effect free and needs no parameters.
        """
        start = time.perf_counter()
        try:
            await self._call("getHealth", [], max_retries=0)
        except Exception as e:  # noqa: BLE001 - health must never raise
            return {
                "provider": self.name,
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "detail": str(e)[:200],
            }
        return {
            "provider": self.name,
            "ok": True,
            "status_code": 200,
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "detail": "reachable",
        }

    async def _call(self, method: str, params: list, max_retries: int = 2) -> dict:
        client = await self._get_client()
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            async with self._lock:
                now = time.monotonic()
                wait = self._last_call + self._min_interval - now
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_call = time.monotonic()
            self._req_id += 1
            payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params}
            start = time.perf_counter()
            try:
                resp = await client.post(self.url, json=payload)
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code in (429,) or resp.status_code >= 500:
                    last_exc = ProviderError(self.name, f"HTTP {resp.status_code}", {"method": method})
                    if attempt < max_retries:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise last_exc
                resp.raise_for_status()
                data = resp.json()
                if data.get("error"):
                    raise ProviderError(
                        self.name, f"rpc error: {data['error']}", {"method": method}
                    )
                from app.services.provider_service import record_provider_health

                record_provider_health(self.name, latency_ms=latency, ok=True)
                return data.get("result", {})
            except (httpx.TimeoutException, httpx.TransportError, ValueError) as e:
                last_exc = e
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
        from app.services.provider_service import record_provider_health

        record_provider_health(self.name, ok=False, error=str(last_exc))
        raise ProviderError(self.name, f"rpc failed: {last_exc}", {"method": method})

    async def get_mint_info(self, mint: str) -> dict:
        """Return {mint_authority, freeze_authority, supply, decimals} (None when unknown)."""
        result = await self._call(
            "getAccountInfo", [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}]
        )
        value = (result.get("value") or {})
        parsed = ((value.get("data") or {}).get("parsed") or {}) if isinstance(value, dict) else {}
        info = parsed.get("info") or {}
        if not info:
            return {
                "mint_authority": None,
                "freeze_authority": None,
                "supply": None,
                "decimals": None,
                "found": bool(value),
            }
        return {
            "mint_authority": info.get("mintAuthority"),
            "freeze_authority": info.get("freezeAuthority"),
            "supply": info.get("supply"),
            "decimals": info.get("decimals"),
            "is_frozen": info.get("isFrozen"),
            "program": info.get("program"),
            "found": True,
        }

    async def get_top_holder_balances(self, mint: str, limit: int = 20) -> list[int]:
        """Raw token balances of the largest token accounts, descending.

        `getTokenLargestAccounts` returns only the accounts; the balances need a
        follow-up `getMultipleAccounts` to be usable. Returns raw atomic units
        so no float precision is lost.
        """
        result = await self._call(
            "getTokenLargestAccounts",
            [mint, {"commitment": "confirmed", "limit": max(1, min(20, limit))}],
        )
        accounts = [a for a in (result.get("value") or []) if isinstance(a, dict) and a.get("address")]
        if not accounts:
            return []

        balances: list[int] = []
        # getMultipleAccounts accepts at most 100 accounts.
        for chunk_start in range(0, len(accounts), 100):
            chunk = accounts[chunk_start : chunk_start + 100]
            addresses = [a["address"] for a in chunk]
            parsed = await self._call(
                "getMultipleAccounts",
                [addresses, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            )
            for item in parsed.get("value") or []:
                if not isinstance(item, dict):
                    continue
                info = (((item.get("data") or {}).get("parsed") or {}).get("info") or {})
                raw = (info.get("tokenAmount") or {}).get("amount")
                if raw is None:
                    continue
                try:
                    balances.append(int(raw))
                except (TypeError, ValueError):
                    continue
        return balances

    async def collect_token_facts(self, mint: str, holder_limit: int = 20) -> dict:
        """Full on-chain picture for one mint.

        Returns a dict whose safety fields are None when they could NOT be
        verified. A provider failure yields `status=ERROR`, never a False
        (which would read as "authority revoked").
        """
        from app.core.errors import ProviderError

        try:
            mint_info = await self.get_mint_info(mint)
        except ProviderError as exc:
            return {
                "status": "ERROR",
                "error": str(exc)[:500],
                "mint_authority_revoked": None,
                "freeze_authority_revoked": None,
                "supply_raw": None,
                "decimals": None,
                "top10_holder_pct": None,
                "top20_holder_pct": None,
                "holder_accounts_scanned": 0,
                "is_frozen": None,
                "provider": self.name,
            }

        if not mint_info.get("found"):
            return {
                "status": "NOT_FOUND",
                "error": "mint account not found on chain",
                "mint_authority_revoked": None,
                "freeze_authority_revoked": None,
                "supply_raw": None,
                "decimals": None,
                "top10_holder_pct": None,
                "top20_holder_pct": None,
                "holder_accounts_scanned": 0,
                "is_frozen": None,
                "provider": self.name,
            }

        mint_authority = mint_info.get("mint_authority")
        freeze_authority = mint_info.get("freeze_authority")
        # A non-empty authority string means the authority still exists.
        mint_revoked = None if mint_authority is None else (mint_authority == "")
        freeze_revoked = None if freeze_authority is None else (freeze_authority == "")

        top10_pct, top20_pct, scanned = _concentration(mint_info.get("supply"), holder_limit)
        if scanned == 0:
            # Holder data unavailable; concentration stays unknown rather than 0.
            top10_pct, top20_pct, scanned = await self._holder_concentration(
                mint, mint_info.get("supply")
            )

        return {
            "status": "OK",
            "error": None,
            "mint_authority_revoked": mint_revoked,
            "freeze_authority_revoked": freeze_revoked,
            "supply_raw": str(mint_info.get("supply")) if mint_info.get("supply") is not None else None,
            "decimals": mint_info.get("decimals"),
            "top10_holder_pct": top10_pct,
            "top20_holder_pct": top20_pct,
            "holder_accounts_scanned": scanned,
            "is_frozen": mint_info.get("is_frozen"),
            "provider": self.name,
        }

    async def _holder_concentration(
        self, mint: str, supply_raw: str | None
    ) -> tuple[float | None, float | None, int]:
        from app.core.errors import ProviderError

        try:
            balances = await self.get_top_holder_balances(mint)
        except ProviderError:
            return None, None, 0
        return _concentration(supply_raw, len(balances), balances)


def _concentration(
    supply_raw: str | None, scanned_hint: int, balances: list[int] | None = None
) -> tuple[float | None, float | None, int]:
    """Top-10 / top-20 share of supply as a 0..1 fraction.

    Returns (None, None, 0) when supply or balances are unavailable: an unknown
    concentration must stay unknown, never be reported as 0%.
    """
    if balances is None or supply_raw is None:
        return None, None, 0
    try:
        supply = int(supply_raw)
    except (TypeError, ValueError):
        return None, None, 0
    if supply <= 0 or not balances:
        return None, None, 0
    ordered = sorted(balances, reverse=True)
    top10 = sum(ordered[:10]) / supply
    top20 = sum(ordered[:20]) / supply
    # Clamp: rounding and rounding-error can push this a hair above 1.0.
    return min(1.0, round(top10, 6)), min(1.0, round(top20, 6)), len(ordered)
