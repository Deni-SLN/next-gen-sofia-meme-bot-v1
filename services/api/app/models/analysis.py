from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, utcnow, uuid_str


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # PASS|WARN|REJECT|UNKNOWN
    hard_reject: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_flags: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    pair_id: Mapped[str | None] = mapped_column(ForeignKey("token_pairs.id"))
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scoring_config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    risk_assessment_id: Mapped[str | None] = mapped_column(ForeignKey("risk_assessments.id"))
    score: Mapped[float | None] = mapped_column(Float)
    coverage: Mapped[float | None] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="WAIT")
    reasons: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    indicators: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    provider_versions: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    ai_summary: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    pair_id: Mapped[str] = mapped_column(ForeignKey("token_pairs.id"), nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)  # LONG_CANDIDATE...
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="CREATED")
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    entry_reference: Mapped[float | None] = mapped_column(Float)
    stop_reference: Mapped[float | None] = mapped_column(Float)
    target_references: Mapped[list | None] = mapped_column(JSONType)
    fee_assumptions: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    slippage_assumption: Mapped[float | None] = mapped_column(Float)
    risk_reward: Mapped[float | None] = mapped_column(Float)
    invalidation_conditions: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage: Mapped[float | None] = mapped_column(Float)
    risk_flags: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    source_references: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    signature: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False, index=True)
    horizon: Mapped[str] = mapped_column(String(16), nullable=False)
    return_pct: Mapped[float | None] = mapped_column(Float)
    net_return_pct: Mapped[float | None] = mapped_column(Float)
    mae: Mapped[float | None] = mapped_column(Float)
    mfe: Mapped[float | None] = mapped_column(Float)
    evaluation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
