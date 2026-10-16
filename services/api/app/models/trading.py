from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, utcnow, uuid_str


class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_strategy_name_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class BotRun(Base):
    __tablename__ = "bot_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # PAPER | LIVE
    strategy_id: Mapped[str | None] = mapped_column(ForeignKey("strategies.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by: Mapped[str | None] = mapped_column(String(64))
    stop_reason: Mapped[str | None] = mapped_column(String(256))


class OrderIntent(Base):
    __tablename__ = "order_intents"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_order_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    bot_run_id: Mapped[str] = mapped_column(ForeignKey("bot_runs.id"), nullable=False)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False, default="BUY")
    requested_size: Mapped[float | None] = mapped_column(Float)  # USD
    reference_price: Mapped[float | None] = mapped_column(Float)
    risk_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_reasons: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INTENT_CREATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    # References order_intents.id. A fill must never reference anything else;
    # SQLite foreign keys are enabled so a wrong id fails instead of persisting.
    order_id: Mapped[str] = mapped_column(ForeignKey("order_intents.id"), nullable=False, index=True)
    position_id: Mapped[str | None] = mapped_column(String(36), index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False, default="BUY")
    fill_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    fee_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fee_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fill_type: Mapped[str] = mapped_column(String(16), nullable=False, default="SIMULATED")
    filled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    bot_run_id: Mapped[str] = mapped_column(ForeignKey("bot_runs.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    # The order intent that opened this position. Required so every fill - the
    # entry fill and the exit fill - can be traced back to an order (FR-TB-008).
    # Foreign keys are named explicitly: Alembic batch mode on SQLite cannot
    # create an unnamed constraint.
    open_order_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("order_intents.id", name="fk_positions_open_order_intent_id")
    )
    open_signal_id: Mapped[str | None] = mapped_column(
        ForeignKey("signals.id", name="fk_positions_open_signal_id")
    )
    exit_order_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("order_intents.id", name="fk_positions_exit_order_intent_id")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Nullable on purpose. NULL means "not valued yet" - it is never 0.0,
    # because a 0.0 would flow into equity/HWM/drawdown as if the position
    # were worth exactly cost basis. See app.accounting.valuation.
    unrealized_pnl: Mapped[float | None] = mapped_column(Float)
    mark_price: Mapped[float | None] = mapped_column(Float)
    valuation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    valuation_reason: Mapped[str | None] = mapped_column(String(64))
    valuation_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float | None] = mapped_column(Float)
    close_reason: Mapped[str | None] = mapped_column(String(64))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountingEvent(Base):
    __tablename__ = "accounting_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_accounting_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(32))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
