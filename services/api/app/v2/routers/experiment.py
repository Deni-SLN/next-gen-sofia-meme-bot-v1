"""
Phase 6: Three-Strategy Comparative Experiment Router (PRD Section 18 & CEO Directive Phase 6).
Exposes REST endpoints to inspect comparative scorecards across Strategy A (V1), Strategy B (V2 Rule-Based),
and Strategy C (V2 AI Autonomous), query position lifecycles, and run synchronized candidate simulations.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Trade
from app.v2.services.paper_experiment import ThreeStrategyExperiment
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator
from app.v2.feedback.optimizer import ParameterOptimizer

router = APIRouter()


@router.get("/scorecard")
def get_three_strategy_scorecard(db: Session = Depends(get_db)):
    """
    Returns the comprehensive 17-metric comparative scorecard across:
    - Strategy A: V1 Deterministic (Control Group)
    - Strategy B: V2 Rule-Based (Deterministic Architecture)
    - Strategy C: V2 AI Autonomous (Full AI Multi-Agent System)
    Calculated 100% from complete position lifecycles (Rule 1 Zero Dummy Data).
    """
    return ThreeStrategyExperiment.generate_comparative_scorecard(db=db)


@router.get("/lifecycles")
def get_position_lifecycles(
    mode: Optional[str] = Query(None, description="PAPER_V1, PAPER_V2_RULE, or PAPER_V2_AI"),
    status: Optional[str] = Query(None, description="OPEN or CLOSED"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Retrieves aggregated position lifecycles with unified entry costs, partial exit legs,
    net lifecycle PnL, and profit capture ratio.
    """
    target_mode = mode.upper() if mode else "PAPER"
    lifecycles = LifecycleAggregator.aggregate_lifecycles(db=db, mode=target_mode)
    if status:
        lifecycles = [lc for lc in lifecycles if lc.status == status.upper()]

    return [
        {
            "symbol": lc.symbol,
            "mode": lc.mode,
            "status": lc.status,
            "is_win": lc.is_win,
            "entry_quantity": lc.entry_quantity,
            "entry_price": lc.entry_price,
            "total_entry_cost_usd": lc.total_entry_cost_usd,
            "total_exit_proceeds_usd": lc.total_exit_proceeds_usd,
            "net_pnl_usd": lc.net_pnl_usd,
            "net_pnl_pct": lc.net_pnl_pct,
            "partial_exits_count": lc.partial_exits_count,
            "profit_capture_ratio": lc.profit_capture_ratio,
            "holding_time_seconds": lc.holding_time_seconds,
            "mfe_pct": lc.mfe_pct,
            "mae_pct": lc.mae_pct,
            "exit_reasons": lc.exit_reasons,
            "exit_trades": lc.exit_trades,
            "contemporaneous_regime": lc.contemporaneous_regime,
        }
        for lc in lifecycles[:limit]
    ]


@router.post("/evaluate-candidate")
def evaluate_candidate_across_strategies(
    candidate: Dict[str, Any],
    contemporaneous_regime: str = Query("ranging", description="Contemporaneous regime (trending, ranging, choppy)"),
    db: Session = Depends(get_db),
):
    """
    Simultaneously evaluates a token candidate across all three strategies with synchronized market data.
    """
    return ThreeStrategyExperiment.simulate_candidate_evaluation(
        candidate=candidate,
        db=db,
        contemporaneous_regime=contemporaneous_regime,
    )


@router.get("/regimes")
def get_contemporaneous_regime_comparison(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode"),
    db: Session = Depends(get_db),
):
    """
    Returns closed trade performance segmented by contemporaneous market regime (Correction 4).
    """
    return ParameterOptimizer.segment_by_market_regime(db=db, mode=mode.upper())


@router.get("/walk-forward")
def get_walk_forward_validation_report(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode"),
    db: Session = Depends(get_db),
):
    """
    Runs chronological walk-forward analysis with zero data leakage (Correction 6).
    """
    trades = list(
        db.scalars(
            select(Trade).where(
                Trade.status == "closed",
                Trade.side == "sell",
                Trade.mode == mode.upper(),
            ).order_by(Trade.opened_at.asc(), Trade.id.asc())
        ).all()
    )

    return ParameterOptimizer.run_walk_forward_optimization(trades=trades, train_test_split=0.70)
