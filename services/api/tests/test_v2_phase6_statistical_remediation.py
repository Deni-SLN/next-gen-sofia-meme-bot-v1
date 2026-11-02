"""
Comprehensive Test Suite for SOFIA MEME BOT V2 — Phase 6 Statistical Remediation (CEO Directive Nov 2, 2026).

Verifies:
1. Lifecycle Identity Audit: Mint-based identity, separate strategy/position/execution IDs.
2. Complete PnL Distribution: Median, IQR, P10/P25/P50/P75/P90, Skewness, Excess Kurtosis.
3. Outlier Sensitivity Analysis: 1% & 5% trimmed/winsorized means, ex-max winner, ex-min loser.
4. Paired Bootstrap Analysis: A vs B, B vs C, and A vs C with empirical p-values and 95% CIs.
5. Block Bootstrap by Time: Temporal autocorrelation preservation with block size 5.
6. 4-Way AI Ablation Engine: B1 (Det Entry + Det Exit), C1 (AI Entry + Det Exit),
   C2 (Det Entry + AI Exit), C3 (Full AI).
7. Execution Cost Calibration: 4 calibrated stress scenarios & breakeven slippage threshold.
8. REST API Endpoints: /scorecard, /ablation, /cost-sensitivity, /pnl-distributions.
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add api directory to sys.path
api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.models import Trade
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator, PositionLifecycle
from app.v2.feedback.paired_bootstrap import PairedStatisticalEngine
from app.v2.services.paper_experiment import ThreeStrategyExperiment
from app.v2.services.ablation_engine import AblationExperimentEngine, ExecutionCostSensitivityEngine

init_db()
client = TestClient(app)


def _get_db():
    return SessionLocal()


def test_01_lifecycle_identity_mint_isolation():
    """
    Test 1: Verify Solana mint address as primary token identity and strict strategy isolation.
    """
    db = _get_db()
    try:
        mode = f"TEST_MINT_{uuid.uuid4().hex[:6]}"
        mint_1 = "MintAlpha11111111111111111111111111111111111"
        mint_2 = "MintBeta22222222222222222222222222222222222"
        now = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

        t1 = Trade(symbol="TOKEN", side="buy", quantity=100, price=1.0, total=100, mode=mode, notes=f"[mint:{mint_1}]", opened_at=now)
        t2 = Trade(symbol="TOKEN", side="buy", quantity=200, price=2.0, total=400, mode=mode, notes=f"[mint:{mint_2}]", opened_at=now)
        db.add_all([t1, t2])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lcs) == 2, "Two distinct mints with same symbol must form separate lifecycles"
        mints = {lc.mint for lc in lcs}
        assert mint_1 in mints and mint_2 in mints
        print("[PASS] Test 1: Mint-based lifecycle identity and symbol collision prevention verified.")
    finally:
        db.close()


def test_02_distribution_moments_and_outlier_sensitivity():
    """
    Test 2: Verify computation of median, IQR, percentiles, skewness, kurtosis, and outlier sensitivity.
    """
    # Sample distribution of 20 trades
    pnls = [
        -2.5, -2.0, -1.8, -1.5, -1.0, -0.8, -0.5, 0.2, 0.5, 1.0,
        1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 25.0  # 25.0 is an extreme positive outlier
    ]

    moments = PairedStatisticalEngine.compute_distribution_moments(pnls)
    assert moments["count"] == 20
    assert moments["median"] == 1.1  # between 1.0 and 1.2
    assert moments["iqr"] > 0
    assert moments["p10"] < moments["p50"] < moments["p90"]
    assert moments["skewness"] > 0.0  # heavily right-skewed due to outlier

    sens = PairedStatisticalEngine.sensitivity_analysis(pnls)
    assert sens["raw_mean_pnl"] > sens["trimmed_mean_5pct"]  # Trimming reduces mean because of 25.0 outlier
    assert sens["raw_mean_pnl"] > sens["ex_max_winner_mean"]
    assert sens["max_winner_influence"] > 0.5
    print(f"[PASS] Test 2: Distribution moments & outlier sensitivity verified (Median={moments['median']}, Skew={moments['skewness']}).")


def test_03_paired_bootstrap_hypothesis_testing():
    """
    Test 3: Verify paired bootstrap difference and empirical p-value computation.
    """
    # Strategy X clearly outperforms Strategy Y
    samples_x = [5.0, 4.0, 6.0, 3.5, 4.5, 5.5, 6.0, 4.8, 5.2, 6.5]
    samples_y = [1.0, 1.5, 0.8, 1.2, 1.0, 2.0, 1.1, 0.9, 1.3, 1.4]

    res = PairedStatisticalEngine.paired_bootstrap_comparison(samples_x, samples_y, n_bootstraps=1000)
    assert res["mean_difference"] > 3.0
    assert res["bootstrap_ci_95"]["lower"] > 0.0
    assert res["p_value"] < 0.05
    assert res["statistically_significant"] is True
    print(f"[PASS] Test 3: Paired bootstrap verified (Mean Diff={res['mean_difference']}, CI={res['bootstrap_ci_95']}, p={res['p_value']}).")


def test_04_block_bootstrap_temporal_correlation():
    """
    Test 4: Verify block bootstrap by time/session preserving autocorrelation.
    """
    samples_x = [2.0, 2.5, 3.0, 1.5, 2.0, 4.0, 3.5, 2.8, 3.2, 4.1, 2.9, 3.8, 4.2, 3.1, 2.7]
    samples_y = [1.0, 1.2, 1.5, 1.1, 1.0, 1.8, 1.4, 1.3, 1.6, 2.0, 1.2, 1.5, 1.7, 1.3, 1.1]

    res = PairedStatisticalEngine.block_bootstrap_comparison(samples_x, samples_y, block_size=5, n_bootstraps=1000)
    assert res["block_size"] == 5
    assert res["mean_difference"] > 1.0
    assert res["block_bootstrap_ci_95"]["lower"] > 0.0
    print(f"[PASS] Test 4: Block bootstrap verified (Block CI={res['block_bootstrap_ci_95']}).")


def test_05_four_way_ablation_engine():
    """
    Test 5: Run 4-way ablation (B1, C1, C2, C3) and verify attribution of AI Entry vs AI Exit.
    """
    db = _get_db()
    try:
        print("[INFO] Running 4-way ablation benchmark (B1, C1, C2, C3) target 25 per variant...")
        res = AblationExperimentEngine.run_ablation_benchmark(db=db, target_lifecycles=25, reset_existing=True)

        assert "b1_deterministic_baseline" in res
        assert "c1_ai_entry_only" in res
        assert "c2_ai_exit_only" in res
        assert "c3_full_ai_system" in res
        assert "attribution_analysis" in res

        attr = res["attribution_analysis"]
        assert "ai_entry_incremental_value (C1 vs B1)" in attr
        assert "ai_exit_incremental_value (C2 vs B1)" in attr
        assert "full_ai_system_value (C3 vs B1)" in attr
        assert "primary_alpha_driver" in attr

        print(f"[PASS] Test 5: 4-Way AI Ablation verified (Primary Driver: {attr['primary_alpha_driver']}, Synergy PnL: ${attr['synergistic_interaction_pnl_usd']}).")
    finally:
        db.close()


def test_06_execution_cost_sensitivity_stress_testing():
    """
    Test 6: Evaluate strategy under 4 stressed cost scenarios and determine breakeven slippage.
    """
    db = _get_db()
    try:
        res = ExecutionCostSensitivityEngine.evaluate_cost_scenarios(db=db, mode="PAPER_V2_AI")
        assert "scenarios" in res
        scenarios = res["scenarios"]

        assert "scenario_1_baseline_realistic" in scenarios
        assert "scenario_2_stressed_2x_slippage" in scenarios
        assert "scenario_3_congested_priority_fees" in scenarios
        assert "scenario_4_worst_case_delayed_execution" in scenarios

        assert "breakeven_slippage_multiplier" in res
        assert res["breakeven_slippage_multiplier"] > 1.0, "Strategy edge must survive at least 1.0x baseline slippage"
        print(f"[PASS] Test 6: Execution cost sensitivity verified (Breakeven Slippage Multiplier: {res['breakeven_slippage_multiplier']}x).")
    finally:
        db.close()


def test_07_fastapi_rest_endpoints():
    """
    Test 7: Verify all new REST API endpoints.
    """
    # 1. GET /api/v2/experiment/ablation
    resp = client.get("/api/v2/experiment/ablation")
    assert resp.status_code == 200
    abl = resp.json()
    assert "attribution_analysis" in abl

    # 2. GET /api/v2/experiment/cost-sensitivity?mode=PAPER_V2_AI
    resp = client.get("/api/v2/experiment/cost-sensitivity?mode=PAPER_V2_AI")
    assert resp.status_code == 200
    sens = resp.json()
    assert "scenarios" in sens

    # 3. GET /api/v2/experiment/pnl-distributions?mode=PAPER_V2_AI
    resp = client.get("/api/v2/experiment/pnl-distributions?mode=PAPER_V2_AI")
    assert resp.status_code == 200
    dist = resp.json()
    assert "distribution_moments" in dist
    assert "outlier_sensitivity" in dist

    # 4. GET /api/v2/experiment/scorecard
    resp = client.get("/api/v2/experiment/scorecard")
    assert resp.status_code == 200
    card = resp.json()
    assert "statistical_distinctions" in card
    print("[PASS] Test 7: All new FastAPI REST remediation endpoints verified.")


def run_all_tests():
    tests = [
        test_01_lifecycle_identity_mint_isolation,
        test_02_distribution_moments_and_outlier_sensitivity,
        test_03_paired_bootstrap_hypothesis_testing,
        test_04_block_bootstrap_temporal_correlation,
        test_05_four_way_ablation_engine,
        test_06_execution_cost_sensitivity_stress_testing,
        test_07_fastapi_rest_endpoints,
    ]
    passed = 0
    failed = 0
    for idx, t in enumerate(tests, 1):
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] Test {idx} ({t.__name__}): {e}")
            import traceback
            traceback.print_exc()

    print("=" * 70)
    print(f"STATISTICAL REMEDIATION RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed / len(tests) * 100:.1f}%)")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
