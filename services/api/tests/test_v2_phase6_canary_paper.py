"""
Phase 6 Final Remediation & Canary PAPER Test Suite (CEO Directive November 2, 2026).
Verifies:
1. Stress test accounting reconciliation & cost/PnL bridge (resolving the +$16.72 discrepancy).
2. Slippage sensitivity sweep (2.0x, 2.1x, 2.2x, 2.25x, 2.3x, 2.4x) and exact breakeven transition.
3. AI Ablation 5-way matrix with 10,000 bootstrap resamples.
4. Canary PAPER Forward Evaluation with 50 market candidates.
5. Priority Fee Circuit Breaker triggering and recovery in PAPER mode.
6. Zero duplicate executions & zero unreconciled positions.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Trade
from app.v2.services.ablation_engine import AblationExperimentEngine, ExecutionCostSensitivityEngine
from app.v2.services.canary_paper import CanaryPaperEngine
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator
from app.v2.feedback.paired_bootstrap import PairedStatisticalEngine


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_01_stress_test_cost_bridge_reconciliation(test_db):
    """
    Test 1: Resolves and documents the Strategy C stress-test figures discrepancy.
    Baseline Net PnL = +$150.47, Baseline Costs = $95.38, Baseline Slippage = $66.88.
    Confirms why flawed calculation produced +$16.72 (subtracting 2x slippage from Net PnL)
    and verifies the corrected stressed PnL of +$83.59.
    """
    bridge = ExecutionCostSensitivityEngine.reconcile_stress_test_accounting(db=test_db, mode="PAPER_V2_AI")

    base = bridge["baseline_accounting"]
    assert base["baseline_net_pnl_usd"] == 150.47
    assert base["total_baseline_costs_usd"] == 95.38
    assert base["baseline_slippage_usd"] == 66.88

    recon = bridge["stress_2x_slippage_reconciliation"]
    assert recon["total_stressed_slippage_2x_usd"] == 133.76
    assert recon["incremental_slippage_addition_usd"] == 66.88
    assert recon["flawed_double_counted_pnl_usd"] == 16.71  # $150.47 - $133.76
    assert recon["corrected_stressed_net_pnl_usd"] == 83.59  # $150.47 - $66.88

    expl = bridge["discrepancy_explanation"]
    assert expl["audit_verdict"] == "DOUBLE_COUNTING_IDENTIFIED"
    assert "twice" in expl["root_cause"].lower()


def test_02_slippage_sensitivity_sweep(test_db):
    """
    Test 2: Verifies sensitivity sweep across 2.0x, 2.1x, 2.2x, 2.25x, 2.3x, and 2.4x.
    Proves that flawed double-counting formula crossed zero at exactly 2.25x,
    whereas corrected formula remains profitable across all multipliers up to 2.4x (breakeven 3.25x).
    """
    sweep = ExecutionCostSensitivityEngine.run_slippage_sweep(
        db=test_db,
        mode="PAPER_V2_AI",
        multipliers=[2.0, 2.1, 2.2, 2.25, 2.3, 2.4]
    )

    grid = sweep["sweep_grid"]
    assert len(grid) == 6

    # Multiplier 2.0x
    assert grid[0]["multiplier"] == 2.0
    assert grid[0]["corrected_net_pnl_usd"] == 83.59
    assert grid[0]["corrected_is_positive"] is True

    # Multiplier 2.25x
    assert grid[3]["multiplier"] == 2.25
    assert grid[3]["corrected_net_pnl_usd"] == 66.87
    assert grid[3]["flawed_net_pnl_usd"] == -0.01 or grid[3]["flawed_net_pnl_usd"] == 0.0  # Near zero crossing

    # Multiplier 2.4x
    assert grid[5]["multiplier"] == 2.4
    assert grid[5]["corrected_net_pnl_usd"] == 56.84
    assert grid[5]["corrected_is_positive"] is True
    assert grid[5]["flawed_is_positive"] is False  # Flawed model fails

    # Breakeven thresholds
    ba = sweep["breakeven_analysis"]
    assert ba["flawed_model_zero_crossing_multiplier"] == 2.25
    assert ba["corrected_model_zero_crossing_multiplier"] == 3.25


def test_03_ai_ablation_five_way_matrix_with_10000_bootstraps(test_db):
    """
    Test 3: Verifies 5-way ablation matrix with 10,000 bootstrap resamples.
    """
    # Seed mock data for B1, C1, C2, C3
    for mode, mean_gain in [("PAPER_ABL_B1", 1.0), ("PAPER_ABL_C1", 1.05), ("PAPER_ABL_C2", 1.30), ("PAPER_ABL_C3", 1.40)]:
        for i in range(20):
            sym = f"T_{i}"
            mint = f"Mint_{mode}_{i}"
            # Buy
            t_buy = Trade(
                symbol=sym, side="buy", quantity=100.0, price=1.0, market_price=1.0, total=100.0,
                mode=mode, status="closed", notes=f"[ranging] [mint:{mint}] BUY", tx_hash=mint,
                opened_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
            )
            test_db.add(t_buy)
            # Sell
            exit_p = 1.0 + (mean_gain / 100.0)
            t_sell = Trade(
                symbol=sym, side="sell", quantity=100.0, price=exit_p, market_price=exit_p, total=100.0 * exit_p,
                mode=mode, status="closed", notes=f"[ranging] [mint:{mint}] SELL FULL", tx_hash=mint,
                opened_at=datetime(2026, 10, 1, 10, 30, tzinfo=timezone.utc),
            )
            test_db.add(t_sell)
    test_db.commit()

    scorecard = AblationExperimentEngine.generate_ablation_scorecard(db=test_db)
    matrix = scorecard["five_way_ablation_matrix"]

    assert "comparison_1_c1_vs_b1" in matrix
    assert "comparison_2_c2_vs_b1" in matrix
    assert "comparison_3_c3_vs_b1" in matrix
    assert "comparison_4_c3_vs_c1" in matrix
    assert "comparison_5_c3_vs_c2" in matrix

    # Verify 10,000 resamples executed
    assert matrix["comparison_1_c1_vs_b1"]["result"]["n_bootstraps"] == 10000
    assert matrix["comparison_3_c3_vs_b1"]["result"]["seed"] == 42


def test_04_canary_paper_50_candidates_run(test_db):
    """
    Test 4: Runs Canary PAPER forward evaluation with 50 candidates.
    Verifies candidate accounting, lifecycles, and zero duplicate/unreconciled positions.
    """
    scorecard = CanaryPaperEngine.run_canary_evaluation(
        db=test_db,
        total_candidates=50,
        simulate_circuit_breaker=True,
        reset_existing=True,
    )

    meta = scorecard["evaluation_metadata"]
    assert meta["total_candidates_screened"] == 50
    assert meta["execution_mode"] == "STRICT_PAPER_ONLY"
    assert meta["parameters_frozen"] is True

    cand_acc = scorecard["candidate_selection_accounting"]
    assert cand_acc["total_screened"] == 50
    assert cand_acc["strategy_a"]["accepted"] > 0
    assert cand_acc["strategy_b"]["accepted"] > 0
    assert cand_acc["strategy_c"]["accepted"] > 0

    audit = scorecard["audit_and_integrity_verification"]
    assert audit["total_unreconciled_positions"] == 0
    assert audit["unreconciled_status"] == "ZERO_UNRECONCILED"
    assert audit["duplicate_execution_errors"] == 0
    assert audit["duplicate_status"] == "ZERO_DUPLICATES"

    # Verify performance metrics exist for all 3 strategies
    perf = scorecard["performance_by_strategy"]
    assert perf["strategy_a_v1"]["lifecycles_count"] > 0
    assert perf["strategy_b_v2_det"]["lifecycles_count"] > 0
    assert perf["strategy_c_v2_ai"]["lifecycles_count"] > 0

    # Verify costs reconciliation
    for s_key in ["strategy_a_v1", "strategy_b_v2_det", "strategy_c_v2_ai"]:
        costs = perf[s_key]["execution_costs"]
        assert costs["network_fees_usd"] > 0.0
        assert costs["priority_fees_usd"] > 0.0
        assert costs["dex_fees_usd"] > 0.0
        assert costs["slippage_usd"] > 0.0
        assert costs["total_costs_usd"] > 0.0


def test_05_canary_priority_fee_circuit_breaker(test_db):
    """
    Test 5: Verifies Priority Fee Circuit Breaker logs and halts.
    """
    scorecard = CanaryPaperEngine.run_canary_evaluation(
        db=test_db,
        total_candidates=30,
        simulate_circuit_breaker=True,
        reset_existing=True,
    )

    cb_logs = scorecard["logs"]["circuit_breaker_logs"]
    assert len(cb_logs) >= 2  # At least TRIGGERED and RESOLVED
    assert cb_logs[0]["event"] == "CIRCUIT_BREAKER_TRIGGERED"
    assert cb_logs[0]["priority_fee_usd"] > 0.050
    assert cb_logs[1]["event"] == "CIRCUIT_BREAKER_RESOLVED"

    # Verify rejected candidate journal records circuit breaker rejections
    rej_full = scorecard["logs"]["rejected_candidates_journal"]
    cb_rejections = [r for r in rej_full if "Circuit Breaker Active" in r["reason"]]
    assert len(cb_rejections) > 0


def test_06_canary_market_regime_breakdown(test_db):
    """
    Test 6: Verifies contemporaneous market regime segmentation in Canary evaluation.
    """
    scorecard = CanaryPaperEngine.run_canary_evaluation(
        db=test_db,
        total_candidates=40,
        simulate_circuit_breaker=False,
        reset_existing=True,
    )

    strat_c = scorecard["performance_by_strategy"]["strategy_c_v2_ai"]
    regimes = strat_c["market_regime_breakdown"]
    assert "trending" in regimes
    assert "ranging" in regimes
    assert "choppy" in regimes
    assert "UNKNOWN" in regimes
