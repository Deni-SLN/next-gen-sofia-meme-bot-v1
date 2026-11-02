"""
Feedback & Learning Engine Router (PRD Section 9 & 13).
Exposes REST APIs for Decision Journals, Performance Metrics, Walk-Forward Optimization,
and Market Regime Segmentation.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Trade
from app.v2.feedback.evaluator import TradeEvaluator
from app.v2.feedback.journal_service import JournalService
from app.v2.feedback.optimizer import ParameterOptimizer
from app.v2.ai.schemas import PerformanceScorecard, DecisionJournalItem, OptimizationResult

router = APIRouter()


@router.get("/metrics", response_model=PerformanceScorecard)
def get_performance_metrics(
    mode: str = Query("PAPER", description="Execution mode: PAPER or LIVE"),
    db: Session = Depends(get_db),
):
    """
    Returns complete performance scorecard (Winrate, Profit Factor, Expectancy, Max Drawdown,
    MFE/MAE averages, Capture Ratio, False Positive Rate).
    Strictly computed 100% from database trade records (Zero Dummy Data).
    """
    return TradeEvaluator.calculate_scorecard(db=db, mode=mode.upper())


@router.get("/journal", response_model=List[DecisionJournalItem])
def get_decision_journals(
    mode: Optional[str] = Query(None, description="PAPER or LIVE"),
    symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Retrieves paginated decision journal entries with post-mortem learning summaries.
    """
    journals = JournalService.get_journals(db=db, mode=mode.upper() if mode else None, symbol=symbol, limit=limit, offset=offset)
    return [
        DecisionJournalItem(
            id=j.id,
            trade_id=j.trade_id,
            symbol=j.symbol,
            mint=j.mint,
            mode=j.mode,
            entry_score=j.entry_score,
            exit_score=j.exit_score,
            initial_risk_pct=j.initial_risk_pct,
            mfe_pct=j.mfe_pct,
            mae_pct=j.mae_pct,
            profit_capture_ratio=j.profit_capture_ratio,
            final_realized_pnl_usd=j.final_realized_pnl_usd,
            final_realized_pnl_pct=j.final_realized_pnl_pct,
            exit_reason=j.exit_reason,
            ai_post_mortem=j.ai_post_mortem,
            lessons_learned=j.lessons_learned,
            created_at=j.created_at.isoformat() if j.created_at else None,
        )
        for j in journals
    ]


@router.get("/journal/{trade_id}", response_model=DecisionJournalItem)
def get_journal_detail(
    trade_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetches the decision journal and post-mortem evaluation for a specific trade.
    """
    j = JournalService.get_journal_by_trade_id(db=db, trade_id=trade_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"No decision journal found for trade_id {trade_id}")
    return DecisionJournalItem(
        id=j.id,
        trade_id=j.trade_id,
        symbol=j.symbol,
        mint=j.mint,
        mode=j.mode,
        entry_score=j.entry_score,
        exit_score=j.exit_score,
        initial_risk_pct=j.initial_risk_pct,
        mfe_pct=j.mfe_pct,
        mae_pct=j.mae_pct,
        profit_capture_ratio=j.profit_capture_ratio,
        final_realized_pnl_usd=j.final_realized_pnl_usd,
        final_realized_pnl_pct=j.final_realized_pnl_pct,
        exit_reason=j.exit_reason,
        ai_post_mortem=j.ai_post_mortem,
        lessons_learned=j.lessons_learned,
        created_at=j.created_at.isoformat() if j.created_at else None,
    )


@router.post("/evaluate/{trade_id}", response_model=DecisionJournalItem)
def evaluate_trade(
    trade_id: int,
    db: Session = Depends(get_db),
):
    """
    Evaluates a closed trade on demand and writes its post-mortem to the Decision Journal.
    """
    trade = db.scalars(select(Trade).where(Trade.id == trade_id)).first()
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

    j = TradeEvaluator.evaluate_and_record_trade(trade=trade, db=db)
    return DecisionJournalItem(
        id=j.id,
        trade_id=j.trade_id,
        symbol=j.symbol,
        mint=j.mint,
        mode=j.mode,
        entry_score=j.entry_score,
        exit_score=j.exit_score,
        initial_risk_pct=j.initial_risk_pct,
        mfe_pct=j.mfe_pct,
        mae_pct=j.mae_pct,
        profit_capture_ratio=j.profit_capture_ratio,
        final_realized_pnl_usd=j.final_realized_pnl_usd,
        final_realized_pnl_pct=j.final_realized_pnl_pct,
        exit_reason=j.exit_reason,
        ai_post_mortem=j.ai_post_mortem,
        lessons_learned=j.lessons_learned,
        created_at=j.created_at.isoformat() if j.created_at else None,
    )


@router.post("/batch-evaluate")
def batch_evaluate_trades(
    mode: str = Query("PAPER", description="Execution mode: PAPER or LIVE"),
    db: Session = Depends(get_db),
):
    """
    Evaluates all unevaluated closed trades in the given mode.
    """
    return JournalService.batch_evaluate_unevaluated_trades(db=db, mode=mode.upper())


@router.post("/optimize", response_model=OptimizationResult)
def run_parameter_optimization(
    mode: str = Query("PAPER", description="Execution mode: PAPER or LIVE"),
    db: Session = Depends(get_db),
):
    """
    Runs walk-forward parameter simulation on historical trades.
    Strictly outputs recommendations with requires_manual_approval=True.
    Never modifies live parameters autonomously.
    """
    trades = list(
        db.scalars(
            select(Trade).where(
                Trade.status == "closed",
                Trade.side == "sell",
                Trade.mode == mode.upper(),
            ).order_by(Trade.closed_at.asc(), Trade.id.asc())
        ).all()
    )

    return ParameterOptimizer.run_walk_forward_optimization(trades=trades)


@router.get("/regimes")
def get_market_regime_breakdown(
    mode: str = Query("PAPER", description="Execution mode: PAPER or LIVE"),
    db: Session = Depends(get_db),
):
    """
    Returns closed trade performance segmented by market regime (trending, ranging, choppy).
    """
    return ParameterOptimizer.segment_by_market_regime(db=db, mode=mode.upper())
