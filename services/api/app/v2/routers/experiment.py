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
from app.v2.services.ablation_engine import AblationExperimentEngine, ExecutionCostSensitivityEngine
from app.v2.services.canary_paper import CanaryPaperEngine
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator
from app.v2.feedback.paired_bootstrap import PairedStatisticalEngine
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
            "position_id": lc.position_id,
            "symbol": lc.symbol,
            "mode": lc.mode,
            "status": lc.status,
            "is_win": lc.is_win,
            "entry_quantity": lc.entry_quantity,
            "entry_price": lc.entry_price,
            "total_entry_cost_usd": lc.total_entry_cost_usd,
            "total_exit_proceeds_usd": lc.total_exit_proceeds_usd,
            "unrealized_cost_usd": lc.unrealized_cost_usd,
            "net_pnl_usd": lc.net_pnl_usd,
            "net_pnl_pct": lc.net_pnl_pct,
            "partial_exits_count": lc.partial_exits_count,
            "profit_capture_ratio": lc.profit_capture_ratio,
            "holding_time_seconds": lc.holding_time_seconds,
            "mfe_pct": lc.mfe_pct,
            "mae_pct": lc.mae_pct,
            "network_fee_usd": lc.network_fee_usd,
            "priority_fee_usd": lc.priority_fee_usd,
            "dex_fee_usd": lc.dex_fee_usd,
            "slippage_cost_usd": lc.slippage_cost_usd,
            "total_execution_costs_usd": lc.total_execution_costs_usd,
            "exit_reasons": lc.exit_reasons,
            "exit_trades": lc.exit_trades,
            "contemporaneous_regime": lc.contemporaneous_regime,
        }
        for lc in lifecycles[:limit]
    ]


@router.post("/run-statistical-benchmark")
def run_statistical_observation_benchmark(
    target_lifecycles: int = Query(100, ge=10, le=200, description="Minimum lifecycles per strategy"),
    reset_existing: bool = Query(True, description="Reset previous benchmark data before running"),
    db: Session = Depends(get_db),
):
    """
    Executes a synchronized, deterministic observation benchmark of at least `target_lifecycles`
    completed position lifecycles per strategy (Strategy A, B, and C).
    Enforces sample size observation (minimum 100 lifecycles) and statistical rigor (Audit Directives 3 & 4).
    """
    return ThreeStrategyExperiment.run_statistical_observation_benchmark(
        db=db,
        target_lifecycles=target_lifecycles,
        reset_existing=reset_existing,
    )


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


@router.post("/run-ablation")
def run_four_way_ablation_benchmark(
    target_lifecycles: int = Query(100, ge=10, le=200, description="Minimum lifecycles per ablation arm"),
    reset_existing: bool = Query(True, description="Reset previous ablation trades"),
    db: Session = Depends(get_db),
):
    """
    Runs synchronized 4-way ablation benchmark (CEO Directive Section 4):
    - B1: V2 Deterministic Entry + Deterministic Exit
    - C1: AI Entry + Deterministic Exit
    - C2: Deterministic Entry + AI Exit
    - C3: Full AI Entry + Full AI Exit
    """
    return AblationExperimentEngine.run_ablation_benchmark(
        db=db,
        target_lifecycles=target_lifecycles,
        reset_existing=reset_existing,
    )


@router.get("/ablation")
def get_four_way_ablation_scorecard(db: Session = Depends(get_db)):
    """
    Returns the 4-way ablation scorecard measuring incremental contributions of AI Entry vs AI Exit.
    """
    return AblationExperimentEngine.generate_ablation_scorecard(db=db)


@router.get("/cost-sensitivity")
def get_execution_cost_sensitivity(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode to evaluate"),
    db: Session = Depends(get_db),
):
    """
    Evaluates strategy resilience under 4 stressed execution cost scenarios:
    1. Baseline Realistic
    2. 2.0x Stressed Slippage
    3. Network Congestion Spike ($0.10 Priority Fee)
    4. Worst-Case Stressed (2x Slippage + High Fees + 2500ms Latency)
    """
    return ExecutionCostSensitivityEngine.evaluate_cost_scenarios(db=db, mode=mode.upper())


@router.get("/pnl-distributions")
def get_strategy_pnl_distributions(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode"),
    db: Session = Depends(get_db),
):
    """
    Returns full distribution moments (median, IQR, skewness, kurtosis, percentiles)
    and outlier sensitivity analysis (trimmed/winsorized means, ex-max, ex-min).
    """
    lifecycles = [lc for lc in LifecycleAggregator.aggregate_lifecycles(db, mode=mode.upper()) if lc.status == "CLOSED"]
    pnls = [lc.net_pnl_usd for lc in lifecycles]
    return {
        "mode": mode.upper(),
        "lifecycles_count": len(lifecycles),
        "distribution_moments": PairedStatisticalEngine.compute_distribution_moments(pnls),
        "outlier_sensitivity": PairedStatisticalEngine.sensitivity_analysis(pnls),
    }


@router.get("/cost-sensitivity/bridge")
def get_stress_test_reconciliation_bridge(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode"),
    db: Session = Depends(get_db),
):
    """
    Returns the reproducible cost and PnL bridge reconciling the Strategy C stress-test figures
    and explains the double-counting discrepancy behind the +$16.72 reported earlier (CEO Directive Section 2.A).
    """
    return ExecutionCostSensitivityEngine.reconcile_stress_test_accounting(db=db, mode=mode.upper())


@router.get("/cost-sensitivity/slippage-sweep")
def get_slippage_sensitivity_sweep(
    mode: str = Query("PAPER_V2_AI", description="Strategy mode"),
    db: Session = Depends(get_db),
):
    """
    Runs the exact sensitivity sweep across slippage multipliers 2.0x, 2.1x, 2.2x, 2.25x, 2.3x, and 2.4x
    and reports the exact positive-to-negative expectancy transition (CEO Directive Section 2.B).
    """
    return ExecutionCostSensitivityEngine.run_slippage_sweep(db=db, mode=mode.upper())


@router.post("/canary/run")
def run_canary_paper_evaluation(
    total_candidates: int = Query(50, ge=10, le=100, description="Total candidates to evaluate"),
    simulate_circuit_breaker: bool = Query(True, description="Simulate priority fee circuit breaker spike"),
    reset_existing: bool = Query(True, description="Reset previous canary paper trades"),
    db: Session = Depends(get_db),
):
    """
    Executes the Canary PAPER Forward Evaluation across 50 forward market candidates (CEO Directive Section 2).
    Evaluates Strategy A, Strategy B, and Strategy C in parallel with frozen parameters.
    """
    return CanaryPaperEngine.run_canary_evaluation(
        db=db,
        total_candidates=total_candidates,
        simulate_circuit_breaker=simulate_circuit_breaker,
        reset_existing=reset_existing,
    )


@router.get("/canary/scorecard")
def get_canary_paper_scorecard(db: Session = Depends(get_db)):
    """
    Returns the latest Canary PAPER scorecard and audit metrics across Strategy A, B, and C.
    """
    return CanaryPaperEngine.get_latest_scorecard(db=db)
