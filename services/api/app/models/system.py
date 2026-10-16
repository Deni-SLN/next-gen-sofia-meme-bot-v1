from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, uuid_str


class AuthSession(Base, TimestampMixin):
    """Persisted session (FR-TB-002/§3.3). Only the token HASH is stored, so a
    database dump cannot be replayed as a valid session."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="OPERATOR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(256))


class WatchlistItem(Base, TimestampMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "mint_address", name="uq_watch_mint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id"), nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    token_id: Mapped[str | None] = mapped_column(ForeignKey("tokens.id"))
    note: Mapped[str | None] = mapped_column(String(256))


class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_url: Mapped[str | None] = mapped_column(String(256))
    settings_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(String(128))
    last_health_status: Mapped[str | None] = mapped_column(String(16))


class AgentConfig(Base, TimestampMixin):
    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(64))
    model_id: Mapped[str | None] = mapped_column(String(128))
    routing_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="AUTO")
    capabilities: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    context_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=8192)
    fallback_policy: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
