from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, utcnow, uuid_str


class Token(Base, TimestampMixin):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("chain", "mint_address", name="uq_token_chain_mint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    chain: Mapped[str] = mapped_column(String(32), nullable=False, default="solana")
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(128))
    decimals: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSONType)


class TokenPair(Base, TimestampMixin):
    __tablename__ = "token_pairs"
    __table_args__ = (UniqueConstraint("pair_address", name="uq_pair_address"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    pair_address: Mapped[str] = mapped_column(String(64), nullable=False)
    dex_id: Mapped[str | None] = mapped_column(String(64))
    quote_token_address: Mapped[str | None] = mapped_column(String(64))
    pair_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="dexscreener")
    # COMPLETE when every field the pipeline needs is present, INCOMPLETE
    # otherwise (FR-AE-001). Never silently treated as complete.
    data_status: Mapped[str] = mapped_column(String(16), nullable=False, default="COMPLETE")
    missing_fields: Mapped[list | None] = mapped_column(JSONType)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    pair_id: Mapped[str] = mapped_column(ForeignKey("token_pairs.id"), nullable=False, index=True)
    price_usd: Mapped[float | None] = mapped_column(Float)
    liquidity_usd: Mapped[float | None] = mapped_column(Float)
    volume_5m: Mapped[float | None] = mapped_column(Float)
    volume_1h: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)
    buys_5m: Mapped[int | None] = mapped_column(Integer)
    sells_5m: Mapped[int | None] = mapped_column(Integer)
    buys_1h: Mapped[int | None] = mapped_column(Integer)
    sells_1h: Mapped[int | None] = mapped_column(Integer)
    price_change_5m: Mapped[float | None] = mapped_column(Float)
    price_change_1h: Mapped[float | None] = mapped_column(Float)
    price_change_24h: Mapped[float | None] = mapped_column(Float)
    fdv: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    # Rolling cumulative windows as reported by the provider. The pipeline must
    # difference them rather than accumulate them (see market_service).
    volume_5m_cumulative: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="dexscreener")
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("pair_id", "timeframe", "open_time", name="uq_candle_pair_tf_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    pair_id: Mapped[str] = mapped_column(ForeignKey("token_pairs.id"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="observed")
    is_final: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_volume: Mapped[float | None] = mapped_column(Float)
    trades: Mapped[int | None] = mapped_column(BigInteger)


class OnchainTokenFacts(Base):
    """Authoritative on-chain state for a mint (FR-AE-004).

    Safety-critical fields (mint/freeze authority, supply, holder
    concentration) come from Solana RPC only. An LLM must never be able to
    populate this table, so a hallucinated value cannot become a PASS.
    """

    __tablename__ = "onchain_token_facts"
    __table_args__ = (UniqueConstraint("token_id", name="uq_onchain_facts_token"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    # None means "not verified"; True/False means verified either way.
    mint_authority_revoked: Mapped[int | None] = mapped_column(Integer)
    freeze_authority_revoked: Mapped[int | None] = mapped_column(Integer)
    supply_raw: Mapped[str | None] = mapped_column(String(64))
    decimals: Mapped[int | None] = mapped_column(Integer)
    top10_holder_pct: Mapped[float | None] = mapped_column(Float)
    top20_holder_pct: Mapped[float | None] = mapped_column(Float)
    holder_accounts_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_frozen: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="solana_rpc")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OK")
    error: Mapped[str | None] = mapped_column(String(512))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    @property
    def age_seconds(self) -> float:
        observed = self.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        return (datetime.now(UTC) - observed).total_seconds()


class ProviderHealth(Base):
    __tablename__ = "provider_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_message: Mapped[str | None] = mapped_column(String(512))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
