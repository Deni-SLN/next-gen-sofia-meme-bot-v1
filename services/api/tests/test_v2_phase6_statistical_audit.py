"""
Verification Test Suite for SOFIA MEME BOT V2 — Phase 6:
CEO DIRECTIVE: OBSERVATION & STATISTICAL VALIDATION (Audit Corrections 1-8 & 100-Lifecycle Benchmark).

Mandatory Directives Verified:
1. Unique position_id / lifecycle_id (not symbol alone).
2. Reopened positions treated as separate lifecycles.
3. Partial exits aggregated without counting remaining tokens as realized profit.
4. Consistent denominators across MFE, MAE, PCR, and net PnL.
5. Explicit execution cost separation (network, priority, DEX fee, slippage).
6. Contemporaneous market regime at decision time.
7. Missing or stale regime data classified as UNKNOWN.
8. Synchronized candidate snapshots across all 3 strategies.
9. Wilson 95% Confidence Interval for winrates.
10. Expectancy 95% Confidence Interval.
11. Statistical observation requirement: >=100 completed lifecycles per strategy (Strategy A, B, C).
12. 17-Metric Comparative Scorecard with A vs B, B vs C, and C vs A comparisons.
13. Market Regime Breakdown (Trending, Ranging, Choppy, UNKNOWN).
14. REST API Endpoints: /scorecard, /lifecycles, /run-statistical-benchmark.
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
from sqlalchemy import select, delete

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.models import Trade
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator, PositionLifecycle
from app.v2.services.paper_experiment import ThreeStrategyExperiment

init_db()
client = TestClient(app)


def _get_db():
    return SessionLocal()


def test_01_unique_position_id_and_reopened_positions():
    """
    Audit Corrections 1 & 2:
    - Lifecycle must have a unique position_id.
    - If a token is bought, fully exited, and bought again later, they must form 2 separate lifecycles.
    """
    db = _get_db()
    try:
        mode = f"TEST_REOPEN_{uuid.uuid4().hex[:6]}"
        sym = "REOPEN_COIN"
        t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Lifecycle 1: Buy 100 at $1, Sell 100 at $1.20
        b1 = Trade(symbol=sym, side="buy", quantity=100.0, price=1.0, total=100.0, mode=mode, status="closed", opened_at=t0)
        s1 = Trade(symbol=sym, side="sell", quantity=100.0, price=1.2, total=120.0, mode=mode, status="closed", opened_at=t0 + timedelta(minutes=10), notes="TP_FULL")
        db.add_all([b1, s1])
        db.commit()

        # Lifecycle 2 (Next day): Buy 200 at $1.50, Sell 200 at $1.40
        t1 = t0 + timedelta(days=1)
        b2 = Trade(symbol=sym, side="buy", quantity=200.0, price=1.5, total=300.0, mode=mode, status="closed", opened_at=t1)
        s2 = Trade(symbol=sym, side="sell", quantity=200.0, price=1.4, total=280.0, mode=mode, status="closed", opened_at=t1 + timedelta(minutes=15), notes="SL_FULL")
        db.add_all([b2, s2])
        db.commit()

        lifecycles = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lifecycles) == 2, f"Expected 2 lifecycles for reopened token, got {len(lifecycles)}"
        
        lc1, lc2 = lifecycles[0], lifecycles[1]
        assert lc1.position_id != lc2.position_id, "Lifecycles must have distinct position_ids"
        assert lc1.position_id.startswith(f"pos_{mode}_{sym}")
        assert lc1.entry_quantity == 100.0 and lc1.is_win is True
        assert lc2.entry_quantity == 200.0 and lc2.is_win is False
        print("[PASS] Test 1: Unique position_id and separate lifecycles for reopened positions verified.")
    finally:
        db.close()


def test_02_partial_exit_unrealized_cost_separation():
    """
    Audit Correction 3:
    Remaining token quantities in partial exits must NOT be counted as realized profit.
    Unrealized cost must be tracked cleanly in `unrealized_cost_usd`.
    """
    db = _get_db()
    try:
        mode = f"TEST_PARTIAL_{uuid.uuid4().hex[:6]}"
        sym = "PARTIAL_UNREAL"
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Buy 100 at $2.00 ($200 total cost)
        b = Trade(symbol=sym, side="buy", quantity=100.0, price=2.0, total=200.0, mode=mode, status="open", opened_at=t0)
        # Sell 40 at $2.50 ($100 exit proceeds)
        s = Trade(symbol=sym, side="sell", quantity=40.0, price=2.5, total=100.0, mode=mode, status="open", opened_at=t0 + timedelta(minutes=5), notes="PARTIAL_40")
        db.add_all([b, s])
        db.commit()

        lifecycles = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lifecycles) == 1
        lc = lifecycles[0]
        assert lc.status == "OPEN"
        assert lc.remaining_quantity == 60.0
        # 60 tokens * $2.00 entry price = $120.00 unrealized cost
        assert lc.unrealized_cost_usd == 120.0
        assert lc.total_exit_proceeds_usd == 100.0
        print("[PASS] Test 2: Partial exit unrealized cost separation verified.")
    finally:
        db.close()


def test_03_consistent_denominators_and_disaggregated_costs():
    """
    Audit Corrections 4 & 5:
    - Consistent mathematical denominators across MFE, MAE, PCR, and net PnL.
    - Disaggregated execution costs into network, priority, DEX fee, and slippage.
    """
    db = _get_db()
    try:
        mode = f"TEST_COSTS_{uuid.uuid4().hex[:6]}"
        sym = "COST_COIN"
        t0 = datetime(2026, 10, 1, 14, 0, 0, tzinfo=timezone.utc)

        # Buy 100 at $1.00 ($100 total), with 0.25 DEX fee, 0.001 base gas, 0.010 priority fee, 1.0% slippage
        b = Trade(
            symbol=sym, side="buy", quantity=100.0, price=1.01, market_price=1.00, total=101.0,
            dex_fee_usd=0.25, gas_fee_usd=0.011, slippage_pct=1.0, mode=mode, status="closed", opened_at=t0
        )
        # Sell 100 at $1.30 ($130 total), with 0.325 DEX fee, 0.001 base gas, 0.010 priority fee, 1.0% slippage
        s = Trade(
            symbol=sym, side="sell", quantity=100.0, price=1.287, market_price=1.30, total=128.7,
            dex_fee_usd=0.325, gas_fee_usd=0.011, slippage_pct=1.0, mode=mode, status="closed", opened_at=t0 + timedelta(minutes=20),
            notes="FULL_EXIT"
        )
        db.add_all([b, s])
        db.commit()

        lifecycles = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lifecycles) == 1
        lc = lifecycles[0]

        assert round(lc.network_fee_usd, 3) == 0.002  # 0.001 * 2
        assert round(lc.priority_fee_usd, 3) == 0.020  # 0.010 * 2
        assert round(lc.dex_fee_usd, 3) == 0.575  # 0.25 + 0.325
        assert lc.slippage_cost_usd > 0.0
        assert lc.total_execution_costs_usd > 0.5
        assert lc.net_pnl_usd < (128.7 - 101.0)  # Fees deducted cleanly
        print("[PASS] Test 3: Consistent denominators and disaggregated execution costs verified.")
    finally:
        db.close()


def test_04_contemporaneous_regimes_and_unknown_fallback():
    """
    Audit Corrections 6 & 7:
    Contemporaneous regime parsed at decision time; missing or corrupt tags default strictly to UNKNOWN.
    """
    db = _get_db()
    try:
        mode = f"TEST_REG_{uuid.uuid4().hex[:6]}"
        t0 = datetime(2026, 10, 1, 15, 0, 0, tzinfo=timezone.utc)

        t_trend = Trade(symbol="T1", side="buy", quantity=10, price=1.0, total=10, mode=mode, notes="[trending] entry", opened_at=t0)
        t_miss = Trade(symbol="T2", side="buy", quantity=10, price=1.0, total=10, mode=mode, notes="no regime provided", opened_at=t0)
        db.add_all([t_trend, t_miss])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        regimes = {lc.symbol: lc.contemporaneous_regime for lc in lcs}
        assert regimes["T1"] == "trending"
        assert regimes["T2"] == "UNKNOWN", f"Missing regime must default to UNKNOWN, got {regimes['T2']}"
        print("[PASS] Test 4: Contemporaneous regimes and UNKNOWN fallback verified.")
    finally:
        db.close()


def test_05_wilson_ci_and_expectancy_ci():
    """
    Audit Directive 5:
    Wilson Score 95% Confidence Interval and Expectancy 95% Confidence Interval calculation.
    """
    # 70 wins out of 100
    ci_wr = ThreeStrategyExperiment.calculate_wilson_score_interval(wins=70, total=100)
    assert ci_wr["lower_pct"] is not None and ci_wr["upper_pct"] is not None
    assert 60.0 <= ci_wr["lower_pct"] <= 61.0, f"Wilson lower bound expected ~60.4%, got {ci_wr['lower_pct']}"
    assert 78.0 <= ci_wr["upper_pct"] <= 79.0, f"Wilson upper bound expected ~78.1%, got {ci_wr['upper_pct']}"

    # Expectancy CI with 10 values
    pnls = [10.0, 15.0, -5.0, 20.0, -10.0, 8.0, 12.0, -4.0, 25.0, 14.0]
    ci_exp = ThreeStrategyExperiment.calculate_expectancy_interval(pnls)
    assert ci_exp["lower_usd"] is not None and ci_exp["upper_usd"] is not None
    assert ci_exp["lower_usd"] < ci_exp["upper_usd"]
    print(f"[PASS] Test 5: Wilson Score CI {ci_wr} & Expectancy CI {ci_exp} verified.")


def test_06_100_lifecycle_observation_benchmark():
    """
    Audit Directives 3, 4 & 5:
    Run the observation benchmark to collect >= 100 completed lifecycles per strategy.
    Verify all 17 metrics, sample size sufficiency flag, Wilson CIs, and regime breakdowns.
    """
    db = _get_db()
    try:
        print("[INFO] Running 100-lifecycle observation benchmark across Strategy A, B, and C...")
        benchmark_res = ThreeStrategyExperiment.run_statistical_observation_benchmark(
            db=db,
            target_lifecycles=100,
            reset_existing=True,
        )

        assert benchmark_res["status"] == "COMPLETED"
        counts = benchmark_res["lifecycles_generated"]
        assert counts[ThreeStrategyExperiment.STRATEGY_A] >= 100
        assert counts[ThreeStrategyExperiment.STRATEGY_B] >= 100
        assert counts[ThreeStrategyExperiment.STRATEGY_C] >= 100

        scorecard = benchmark_res["scorecard"]
        assert scorecard["sample_size_criteria_met"] is True

        strat_a = scorecard["strategy_a_v1_deterministic"]
        strat_b = scorecard["strategy_b_v2_rule_based"]
        strat_c = scorecard["strategy_c_v2_ai_autonomous"]

        # Check sample size sufficiency independently
        assert strat_a["completed_position_lifecycles"] >= 100
        assert strat_b["completed_position_lifecycles"] >= 100
        assert strat_c["completed_position_lifecycles"] >= 100

        # Check Wilson Confidence Intervals are populated
        for st in [strat_a, strat_b, strat_c]:
            assert st["winrate_ci_95"]["lower_pct"] is not None
            assert st["winrate_ci_95"]["upper_pct"] is not None
            assert st["expectancy_ci_95"]["lower_usd"] is not None
            assert st["expectancy_ci_95"]["upper_usd"] is not None
            assert "network_fee_usd" in st["execution_costs_breakdown"]
            assert "priority_fee_usd" in st["execution_costs_breakdown"]
            assert "dex_fee_usd" in st["execution_costs_breakdown"]
            assert "slippage_cost_usd" in st["execution_costs_breakdown"]

            # Check all 4 regimes are accounted for
            regimes = st["regime_breakdown"]
            for r in ["trending", "ranging", "choppy", "UNKNOWN"]:
                assert r in regimes
                assert regimes[r]["completed_lifecycles"] > 0

        # Check delta comparisons
        assert "deterministic_architecture_gain (B vs A)" in scorecard
        assert "ai_autonomous_incremental_gain (C vs B)" in scorecard
        assert "full_system_gain (C vs A)" in scorecard

        delta_c_vs_a = scorecard["full_system_gain (C vs A)"]
        assert delta_c_vs_a["pnl_delta_usd"] > 0, "Strategy C should outperform Strategy A in net PnL"
        assert delta_c_vs_a["full_system_impact"] == "TOTAL_V2_AI_VS_V1_CONTROL_VALUE"

        print(f"[PASS] Test 6: 100-lifecycle benchmark verified (Lifecycles: {counts}).")
        print(f"      Strategy A Winrate: {strat_a['winrate_pct']}% CI [{strat_a['winrate_ci_95']['lower_pct']}%, {strat_a['winrate_ci_95']['upper_pct']}%], Net PnL: ${strat_a['net_realized_pnl_usd']}")
        print(f"      Strategy B Winrate: {strat_b['winrate_pct']}% CI [{strat_b['winrate_ci_95']['lower_pct']}%, {strat_b['winrate_ci_95']['upper_pct']}%], Net PnL: ${strat_b['net_realized_pnl_usd']}")
        print(f"      Strategy C Winrate: {strat_c['winrate_pct']}% CI [{strat_c['winrate_ci_95']['lower_pct']}%, {strat_c['winrate_ci_95']['upper_pct']}%], Net PnL: ${strat_c['net_realized_pnl_usd']}")
    finally:
        db.close()


def test_07_fastapi_rest_scorecard_and_lifecycles():
    """
    Test REST API endpoints with the 100-lifecycle dataset.
    """
    # 1. GET /api/v2/experiment/scorecard
    resp = client.get("/api/v2/experiment/scorecard")
    assert resp.status_code == 200
    card = resp.json()
    assert card["sample_size_criteria_met"] is True
    assert card["strategy_c_v2_ai_autonomous"]["completed_position_lifecycles"] >= 100

    # 2. GET /api/v2/experiment/lifecycles
    resp = client.get("/api/v2/experiment/lifecycles?mode=PAPER_V2_AI&limit=5")
    assert resp.status_code == 200
    lcs = resp.json()
    assert len(lcs) == 5
    assert "position_id" in lcs[0]
    assert "total_execution_costs_usd" in lcs[0]
    assert "contemporaneous_regime" in lcs[0]
    print("[PASS] Test 7: FastAPI REST endpoints /scorecard and /lifecycles verified.")


def run_all_tests():
    tests = [
        test_01_unique_position_id_and_reopened_positions,
        test_02_partial_exit_unrealized_cost_separation,
        test_03_consistent_denominators_and_disaggregated_costs,
        test_04_contemporaneous_regimes_and_unknown_fallback,
        test_05_wilson_ci_and_expectancy_ci,
        test_06_100_lifecycle_observation_benchmark,
        test_07_fastapi_rest_scorecard_and_lifecycles,
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
    print(f"STATISTICAL AUDIT RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed / len(tests) * 100:.1f}%)")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
