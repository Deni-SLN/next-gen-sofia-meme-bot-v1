"""Wallet models (FR-TB-009, PRD v1.1).

Rules: public addresses only (never private keys/seeds); amounts in
integer ATOMIC base units (lamports / USDC 6-decimals), never binary
float for money; WithdrawalIntent has a UNIQUE idempotency_key;
terminal states are never mutated silently.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, utcnow, uuid_str


class WalletAccount(Base, TimestampMixin):
    __tablename__ = "wallet_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    wallet_role: Mapped[str] = mapped_column(String(8), nullable=False)  # BOT | MAIN
    chain: Mapped[str] = mapped_column(String(16), nullable=False, default="solana")
    public_address: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_allowlisted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")


class WalletBalanceSnapshot(Base):
    __tablename__ = "wallet_balance_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    wallet_account_id: Mapped[str] = mapped_column(ForeignKey("wallet_accounts.id"), nullable=False, index=True)
    asset: Mapped[str] = mapped_column(String(8), nullable=False)  # SOL | USDC
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    balance_atomic: Mapped[int] = mapped_column(Integer, nullable=False)
    spendable_atomic: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rpc_provider: Mapped[str | None] = mapped_column(String(64))
    commitment: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))


class WalletPolicyVersion(Base):
    __tablename__ = "wallet_policy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    sweep_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    allowed_assets: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    reserve_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="DYNAMIC")
    min_sweep_atomic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_transfer_cap_atomic: Mapped[int | None] = mapped_column(Integer)
    daily_cap_atomic: Mapped[int | None] = mapped_column(Integer)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    destination_wallet_id: Mapped[str | None] = mapped_column(ForeignKey("wallet_accounts.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class WithdrawalIntent(Base, TimestampMixin):
    __tablename__ = "withdrawal_intents"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_withdrawal_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MANUAL | AUTO_SWEEP
    source_wallet_id: Mapped[str] = mapped_column(ForeignKey("wallet_accounts.id"), nullable=False)
    destination_wallet_id: Mapped[str] = mapped_column(ForeignKey("wallet_accounts.id"), nullable=False)
    destination_address_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    asset: Mapped[str] = mapped_column(String(8), nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_atomic: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_fee_atomic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_fee_atomic: Mapped[int | None] = mapped_column(Integer)
    reserve_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # optimistic lock
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(512))


class WalletTransfer(Base, TimestampMixin):
    __tablename__ = "wallet_transfers"
    __table_args__ = (UniqueConstraint("withdrawal_intent_id", name="uq_transfer_intent"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    withdrawal_intent_id: Mapped[str] = mapped_column(ForeignKey("withdrawal_intents.id"), nullable=False)
    chain: Mapped[str] = mapped_column(String(16), nullable=False, default="solana")
    transaction_signature: Mapped[str | None] = mapped_column(String(128), unique=True)
    submission_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rpc_provider: Mapped[str | None] = mapped_column(String(64))
    commitment_target: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    reconciliation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")


class ProfitSweepEvent(Base):
    __tablename__ = "profit_sweep_events"
    __table_args__ = (
        UniqueConstraint("close_event_id", "asset", "policy_version", name="uq_sweep_trigger"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    close_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset: Mapped[str] = mapped_column(String(8), nullable=False)
    realized_profit_atomic: Mapped[int] = mapped_column(Integer, nullable=False)
    sweep_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    sweep_amount_atomic: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reserve_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    withdrawal_intent_id: Mapped[str | None] = mapped_column(ForeignKey("withdrawal_intents.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="EVALUATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
