"""
Decision Journal Service (PRD Section 9.2).
Provides querying, aggregation, filtering, and batch post-mortem generation for closed trades.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.models import Trade
from app.v2.db.models import DecisionJournal
from app.v2.feedback.evaluator import TradeEvaluator


class JournalService:
    """
    Manages access and operations on the Decision Journal repository.
    """

    @classmethod
    def get_journals(
        cls,
        db: Session,
        mode: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DecisionJournal]:
        """
        Retrieves paginated decision journal entries.
        """
        stmt = select(DecisionJournal)
        if mode:
            stmt = stmt.where(DecisionJournal.mode == mode)
        if symbol:
            stmt = stmt.where(DecisionJournal.symbol.ilike(f"%{symbol}%"))

        stmt = stmt.order_by(DecisionJournal.created_at.desc(), DecisionJournal.id.desc())
        stmt = stmt.offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    @classmethod
    def get_journal_by_id(cls, db: Session, journal_id: int) -> Optional[DecisionJournal]:
        """
        Fetches single journal by ID.
        """
        return db.scalars(
            select(DecisionJournal).where(DecisionJournal.id == journal_id)
        ).first()

    @classmethod
    def get_journal_by_trade_id(cls, db: Session, trade_id: int) -> Optional[DecisionJournal]:
        """
        Fetches journal linked to a specific closed trade ID.
        """
        return db.scalars(
            select(DecisionJournal).where(DecisionJournal.trade_id == trade_id)
        ).first()

    @classmethod
    def batch_evaluate_unevaluated_trades(cls, db: Session, mode: str = "PAPER") -> Dict[str, Any]:
        """
        Scans closed trades without a journal entry and automatically synthesizes post-mortems.
        """
        # Find all closed sell trades
        closed_trades = list(
            db.scalars(
                select(Trade).where(
                    Trade.status == "closed",
                    Trade.side == "sell",
                    Trade.mode == mode,
                )
            ).all()
        )

        existing_trade_ids = set(
            db.scalars(select(DecisionJournal.trade_id).where(DecisionJournal.trade_id.isnot(None))).all()
        )

        evaluated_count = 0
        for trade in closed_trades:
            if trade.id not in existing_trade_ids:
                TradeEvaluator.evaluate_and_record_trade(trade, db)
                evaluated_count += 1

        return {
            "mode": mode,
            "total_closed_trades": len(closed_trades),
            "newly_evaluated": evaluated_count,
            "total_journals": len(existing_trade_ids) + evaluated_count,
        }
