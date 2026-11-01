"""
Database Models for SOFIA MEME BOT V2.
Extends the existing schema non-destructively to satisfy PRD Section 11 (Database Requirements).
"""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import String, Integer, Float, DateTime, JSON, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class AgentDecision(Base):
    """
    Immutable ledger of every AI decision produced by any agent in V2.
    Ensures complete transparency and auditability (PRD Section 4 & 11).
    """
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(40), index=True)  # entry_intelligence, exit_intelligence, etc.
    target_mint: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)  # BUY, WAIT, SKIP, HOLD, REDUCE, TAKE_PROFIT, FULL_EXIT
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    suggested_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reasoning: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    raw_output: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    input_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # Mandatory: reproducible decision state (Directive Item 12)
    provider: Mapped[str] = mapped_column(String(32), default="openrouter")
    model: Mapped[str] = mapped_column(String(128), default="google/gemini-2.0-flash-exp:free")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EntryAssessment(Base):
    """
    Multi-dimensional scoring and quality gate analysis for token candidates (PRD Section 5).
    """
    __tablename__ = "entry_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("agent_decisions.id"), nullable=True)
    target_mint: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market_structure_score: Mapped[float] = mapped_column(Float, default=0.0)  # max 20
    momentum_score: Mapped[float] = mapped_column(Float, default=0.0)          # max 20
    smart_money_score: Mapped[float] = mapped_column(Float, default=0.0)       # max 20
    liquidity_score: Mapped[float] = mapped_column(Float, default=0.0)         # max 15
    holder_score: Mapped[float] = mapped_column(Float, default=0.0)            # max 15
    narrative_score: Mapped[float] = mapped_column(Float, default=0.0)         # max 10
    total_score: Mapped[float] = mapped_column(Float, default=0.0)             # max 100
    entry_zone_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_zone_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    invalidation_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_rr_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed_quality_gate: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    input_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # Mandatory: reproducible input snapshot
    risk_flags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ExitAssessment(Base):
    """
    Dynamic position evaluation and adaptive exit recommendations (PRD Section 6).
    """
    __tablename__ = "exit_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("agent_decisions.id"), nullable=True)
    position_id: Mapped[str] = mapped_column(String(64), index=True)
    target_mint: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    urgency: Mapped[str] = mapped_column(String(20), default="low")  # low, medium, high, critical
    suggested_sell_pct: Mapped[int] = mapped_column(Integer, default=0)  # 0, 25, 50, 75, 100
    market_conditions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    highest_price_observed: Mapped[float] = mapped_column(Float, default=0.0)
    current_executable_price: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    trailing_stop_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dimensions_score: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    risk_flags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    input_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class DecisionJournal(Base):
    """
    Closed trade performance post-mortem, MFE/MAE calculation and feedback learning (PRD Section 9).
    """
    __tablename__ = "decision_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    mint: Mapped[str] = mapped_column(String(64), default="")
    mode: Mapped[str] = mapped_column(String(10), default="PAPER")
    entry_decision_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exit_decision_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entry_score: Mapped[float] = mapped_column(Float, default=0.0)
    exit_score: Mapped[float] = mapped_column(Float, default=0.0)
    initial_risk_pct: Mapped[float] = mapped_column(Float, default=0.0)
    mfe_pct: Mapped[float] = mapped_column(Float, default=0.0)  # Max Favorable Excursion (% max profit potential)
    mae_pct: Mapped[float] = mapped_column(Float, default=0.0)  # Max Adverse Excursion (% max drawdown during trade)
    profit_capture_ratio: Mapped[float] = mapped_column(Float, default=0.0)  # realized profit / MFE
    final_realized_pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    final_realized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    exit_reason: Mapped[str] = mapped_column(String(80), default="NORMAL_EXIT")
    ai_post_mortem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class PositionEvent(Base):
    """
    Audit log of all position lifecycle events (PRD Section 7).
    """
    __tablename__ = "position_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    mint: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(10), default="PAPER")
    event_type: Mapped[str] = mapped_column(String(40), index=True)  # ENTER, PARTIAL_TP_25, PARTIAL_TP_50, TRAILING_STOP, FULL_EXIT, HARD_SL, RECONCILE
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="")
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
