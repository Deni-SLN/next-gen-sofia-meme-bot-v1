from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, utcnow, uuid_str


class LlmRequest(Base):
    __tablename__ = "llm_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    agent_name: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_model: Mapped[str | None] = mapped_column(String(128))
    actual_model: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    cost_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    request_id: Mapped[str | None] = mapped_column(String(64))
    error_metadata: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    __table_args__ = (UniqueConstraint("dedup_key", name="uq_alert_dedup"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reference_type: Mapped[str | None] = mapped_column(String(32))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="TELEGRAM")
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str | None] = mapped_column(String(1024))
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class SettingEntry(Base, TimestampMixin):
    """Key-value store for runtime operator settings (risk config, scoring weights...)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
