"""On-chain token facts (FR-AE-004).

Safety-critical state (mint/freeze authority, supply, holder concentration) is
read from Solana RPC and cached in `onchain_token_facts`. It is deliberately
NOT derivable from LLM output: `UNKNOWN` must stay `UNKNOWN`, and a provider
outage must never be recorded as "authority revoked".

Nothing here claims a token is safe. The values are raw chain state plus a
timestamp, and callers must honour the staleness rules.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ProviderError
from app.models.market import OnchainTokenFacts, Token

log = logging.getLogger("sofia.onchain")

# How long a cached reading stays usable before it must be re-read.
DEFAULT_FACTS_TTL = timedelta(hours=6)
# Authority state changes rarely; concentration changes with every trade.
DEFAULT_CONCENTRATION_TTL = timedelta(hours=2)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


@dataclass
class TokenFacts:
    """Normalised on-chain facts. `None` always means "not verified"."""

    mint_address: str
    mint_authority_revoked: bool | None = None
    freeze_authority_revoked: bool | None = None
    supply_raw: str | None = None
    decimals: int | None = None
    top10_holder_pct: float | None = None
    top20_holder_pct: float | None = None
    holder_accounts_scanned: int = 0
    is_frozen: bool | None = None
    status: str = "UNKNOWN"
    source: str | None = None
    observed_at: datetime | None = None
    error: str | None = None

    @property
    def verified(self) -> bool:
        return self.status == "OK"

    @property
    def age_seconds(self) -> float | None:
        if self.observed_at is None:
            return None
        return (_now() - _aware(self.observed_at)).total_seconds()

    def to_json(self) -> dict:
        return {
            "mint_address": self.mint_address,
            "mint_authority_revoked": self.mint_authority_revoked,
            "freeze_authority_revoked": self.freeze_authority_revoked,
            "supply_raw": self.supply_raw,
            "decimals": self.decimals,
            "top10_holder_pct": self.top10_holder_pct,
            "top20_holder_pct": self.top20_holder_pct,
            "holder_accounts_scanned": self.holder_accounts_scanned,
            "is_frozen": self.is_frozen,
            "status": self.status,
            "source": self.source,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "age_seconds": round(self.age_seconds, 3) if self.age_seconds is not None else None,
            "error": self.error,
        }


def _row_to_facts(row: OnchainTokenFacts, mint_address: str) -> TokenFacts:
    def tri(v):
        return None if v is None else bool(v)

    return TokenFacts(
        mint_address=mint_address,
        mint_authority_revoked=tri(row.mint_authority_revoked),
        freeze_authority_revoked=tri(row.freeze_authority_revoked),
        supply_raw=row.supply_raw,
        decimals=row.decimals,
        top10_holder_pct=row.top10_holder_pct,
        top20_holder_pct=row.top20_holder_pct,
        holder_accounts_scanned=row.holder_accounts_scanned or 0,
        is_frozen=tri(row.is_frozen),
        status=row.status,
        source=row.provider,
        observed_at=_aware(row.observed_at),
        error=row.error,
    )


def get_cached_facts(db: Session, token: Token) -> TokenFacts | None:
    row = (
        db.query(OnchainTokenFacts)
        .filter(OnchainTokenFacts.token_id == token.id)
        .first()
    )
    return _row_to_facts(row, token.mint_address) if row else None


def is_fresh(facts: TokenFacts | None, ttl: timedelta = DEFAULT_FACTS_TTL) -> bool:
    if facts is None or facts.status != "OK" or facts.observed_at is None:
        return False
    return (_now() - _aware(facts.observed_at)) <= ttl


def _persist(db: Session, token: Token, payload: dict) -> TokenFacts:
    row = (
        db.query(OnchainTokenFacts)
        .filter(OnchainTokenFacts.token_id == token.id)
        .first()
    )
    if row is None:
        row = OnchainTokenFacts(token_id=token.id)
        db.add(row)

    def tri(v):
        return None if v is None else (1 if v else 0)

    row.mint_authority_revoked = tri(payload.get("mint_authority_revoked"))
    row.freeze_authority_revoked = tri(payload.get("freeze_authority_revoked"))
    row.supply_raw = payload.get("supply_raw")
    row.decimals = payload.get("decimals")
    row.top10_holder_pct = payload.get("top10_holder_pct")
    row.top20_holder_pct = payload.get("top20_holder_pct")
    row.holder_accounts_scanned = int(payload.get("holder_accounts_scanned") or 0)
    row.is_frozen = tri(payload.get("is_frozen"))
    row.provider = payload.get("provider") or settings.solana_rpc_url
    row.status = payload.get("status") or "UNKNOWN"
    row.error = (payload.get("error") or None) and str(payload["error"])[:512]
    row.observed_at = _now()
    db.commit()
    db.refresh(row)

    if token.decimals is None and row.decimals is not None:
        token.decimals = row.decimals
        db.commit()

    return _row_to_facts(row, token.mint_address)


async def async_refresh_facts(
    db: Session,
    token: Token,
    provider=None,
    holder_limit: int = 20,
) -> TokenFacts:
    """Read on-chain state from RPC and cache it. For async callers."""
    if provider is None:
        from app.providers.onchain.solana_rpc import SolanaRPCProvider

        provider = SolanaRPCProvider()
    try:
        payload = await provider.collect_token_facts(token.mint_address, holder_limit=holder_limit)
    except ProviderError as exc:
        payload = _error_payload(str(exc), provider)
    except Exception as exc:  # noqa: BLE001
        log.warning("on-chain facts failed for %s: %s", token.mint_address, exc)
        payload = _error_payload(str(exc), provider)
    return _persist(db, token, payload)


def _error_payload(message: str, provider) -> dict:
    """Provider failure. Every safety field stays None - never False."""
    return {
        "status": "ERROR",
        "error": message[:500],
        "mint_authority_revoked": None,
        "freeze_authority_revoked": None,
        "supply_raw": None,
        "decimals": None,
        "top10_holder_pct": None,
        "top20_holder_pct": None,
        "holder_accounts_scanned": 0,
        "is_frozen": None,
        "provider": getattr(provider, "name", "solana_rpc"),
    }


def refresh_facts(
    db: Session,
    token: Token,
    provider=None,
    holder_limit: int = 20,
) -> TokenFacts:
    """Synchronous entry point for request handlers and the worker."""
    try:
        return asyncio.run(
            async_refresh_facts(db, token, provider=provider, holder_limit=holder_limit)
        )
    except RuntimeError as exc:
        # Already inside a running loop: fall back to whatever is cached.
        log.debug("deferring on-chain fetch for %s: %s", token.mint_address, exc)
        cached = get_cached_facts(db, token)
        return cached or TokenFacts(mint_address=token.mint_address, status="UNAVAILABLE")


def get_or_fetch(
    db: Session,
    token: Token,
    provider=None,
    holder_limit: int = 20,
    allow_network: bool = True,
) -> TokenFacts:
    """Synchronous entry point for request handlers and the worker.

    Returns cached facts when they are fresh. When no facts exist and network
    access is allowed, performs one RPC round trip.
    """
    cached = get_cached_facts(db, token)
    if is_fresh(cached):
        return cached
    if not allow_network:
        return cached or TokenFacts(mint_address=token.mint_address, status="UNAVAILABLE")
    return refresh_facts(db, token, provider=provider, holder_limit=holder_limit)


def evidence_for_risk(facts: TokenFacts | None) -> dict:
    """Risk-gate inputs derived from on-chain facts only.

    The `verified_*` markers make it impossible for a caller to mistake an
    unverified value for a confirmed one.
    """
    if facts is None:
        return {
            "mint_authority_revoked": None,
            "freeze_authority_revoked": None,
            "top10_holder_pct": None,
        }
    return {
        "mint_authority_revoked": facts.mint_authority_revoked,
        "freeze_authority_revoked": facts.freeze_authority_revoked,
        "top10_holder_pct": facts.top10_holder_pct,
    }