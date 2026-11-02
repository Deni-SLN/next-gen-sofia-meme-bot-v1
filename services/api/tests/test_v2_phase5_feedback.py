"""
Comprehensive Verification Test Suite for SOFIA MEME BOT V2 — Phase 5:
Feedback Engine, Trade Evaluator, Decision Journal, Post-Mortem,
Metrics Calculation, Walk-Forward Optimization & Market Regime Segmentation.

PRD Section 9, 10, 11, 18, 19.
Rule 1 Compliance: ZERO DUMMY DATA.
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

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.models import Trade
from app.v2.db.models import DecisionJournal, AgentDecision
from app.v2.feedback.evaluator import TradeEvaluator
from app.v2.feedback.optimizer import ParameterOptimizer
from app.v2.feedback.journal_service import JournalService

init_db()
client = TestClient(app)


def _get_db():
    return SessionLocal()


def test_01_zero_dummy_data_empty_state():
    """
    Rule 1 Invariant: If there are no closed sell trades in a mode,
    win_rate_pct and profit_factor MUST be None (never a fabricated 78.5% or 0.0).
    """
    db = _get_db()
    try:
        unique_mode = f"PAPER_EMPTY_{uuid.uuid4().hex[:6]}"
        card = TradeEvaluator.calculate_scorecard(db=db, mode=unique_mode)
        assert card.total_closed_trades == 0
        assert card.total_winning_trades == 0
        assert card.total_losing_trades == 0
        assert card.win_rate_pct is None
        assert card.profit_factor is None
        assert card.net_pnl_usd == 0.0
        assert card.expectancy_usd == 0.0
        print("[PASS] Test 1: Zero dummy data invariant verified (None on empty trades).")
    finally:
        db.close()


def test_02_winrate_and_pnl_calculation():
    """
    Verifies that winrate, net PnL, avg win, and avg loss are calculated 100% from DB Trade rows.
    """
    db = _get_db()
    try:
        mode = f"P5_CALC_{uuid.uuid4().hex[:6]}"
        # Create 3 winners and 1 loser
        t1 = Trade(symbol="WIN1", side="sell", quantity=100, price=1.5, total=150, pnl=50.0, mode=mode, status="closed")
        t2 = Trade(symbol="WIN2", side="sell", quantity=100, price=2.0, total=200, pnl=80.0, mode=mode, status="closed")
        t3 = Trade(symbol="WIN3", side="sell", quantity=100, price=1.2, total=120, pnl=20.0, mode=mode, status="closed")
        t4 = Trade(symbol="LOSS1", side="sell", quantity=100, price=0.7, total=70, pnl=-30.0, mode=mode, status="closed")

        db.add_all([t1, t2, t3, t4])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.total_closed_trades == 4
        assert card.total_winning_trades == 3
        assert card.total_losing_trades == 1
        assert card.win_rate_pct == 75.0  # 3/4 = 75.0%
        assert card.net_pnl_usd == 120.0  # 50 + 80 + 20 - 30 = 120
        assert card.avg_win_usd == 50.0   # (50 + 80 + 20) / 3 = 50.0
        assert card.avg_loss_usd == 30.0  # 30 / 1 = 30.0
        print("[PASS] Test 2: Winrate & Net PnL calculated 100% from database Trade rows.")
    finally:
        db.close()


def test_03_profit_factor_calculation():
    """
    Verifies Profit Factor = Gross Profit / Gross Loss.
    """
    db = _get_db()
    try:
        mode = f"P5_PF_{uuid.uuid4().hex[:6]}"
        t1 = Trade(symbol="PFT1", side="sell", total=100, pnl=100.0, mode=mode, status="closed")
        t2 = Trade(symbol="PFT2", side="sell", total=100, pnl=-25.0, mode=mode, status="closed")
        db.add_all([t1, t2])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        # Gross Profit = 100, Gross Loss = 25 -> PF = 4.0
        assert card.profit_factor == 4.0
        print("[PASS] Test 3: Profit Factor verified (Gross Profit / Gross Loss = 4.0).")
    finally:
        db.close()


def test_04_expectancy_calculation():
    """
    Expectancy = (WinRate * AvgWin) - (LossRate * AvgLoss).
    """
    db = _get_db()
    try:
        mode = f"P5_EXP_{uuid.uuid4().hex[:6]}"
        # 2 trades: 1 win ($100), 1 loss ($40) -> WR = 50%, LR = 50%
        # Expectancy = (0.5 * 100) - (0.5 * 40) = 50 - 20 = $30.0
        t1 = Trade(symbol="EXP1", side="sell", total=100, pnl=100.0, mode=mode, status="closed")
        t2 = Trade(symbol="EXP2", side="sell", total=100, pnl=-40.0, mode=mode, status="closed")
        db.add_all([t1, t2])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.expectancy_usd == 30.0
        print("[PASS] Test 4: Mathematical expectancy verified ($30.0/trade).")
    finally:
        db.close()


def test_05_max_drawdown_peak_to_trough():
    """
    Verifies peak-to-trough maximum drawdown calculation.
    """
    db = _get_db()
    try:
        mode = f"P5_DD_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)
        t1 = Trade(symbol="DD1", side="sell", total=100, pnl=100.0, mode=mode, status="closed", closed_at=now)
        t2 = Trade(symbol="DD2", side="sell", total=100, pnl=-40.0, mode=mode, status="closed", closed_at=now + timedelta(seconds=1))
        t3 = Trade(symbol="DD3", side="sell", total=100, pnl=-30.0, mode=mode, status="closed", closed_at=now + timedelta(seconds=2))
        t4 = Trade(symbol="DD4", side="sell", total=100, pnl=50.0, mode=mode, status="closed", closed_at=now + timedelta(seconds=3))
        db.add_all([t1, t2, t3, t4])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.max_drawdown_usd == 70.0
        assert card.max_drawdown_pct == 70.0
        print("[PASS] Test 5: Peak-to-trough Maximum Drawdown verified ($70.0 / 70.0%).")
    finally:
        db.close()


def test_06_mfe_and_mae_metrics():
    """
    Verifies that MFE and MAE excursion metrics are correctly averaged.
    """
    db = _get_db()
    try:
        mode = f"P5_EXC_{uuid.uuid4().hex[:6]}"
        j1 = DecisionJournal(symbol="EXC1", mode=mode, mfe_pct=40.0, mae_pct=-5.0, profit_capture_ratio=0.75, final_realized_pnl_usd=30.0)
        j2 = DecisionJournal(symbol="EXC2", mode=mode, mfe_pct=20.0, mae_pct=-15.0, profit_capture_ratio=0.50, final_realized_pnl_usd=10.0)
        db.add_all([j1, j2])
        db.commit()

        # Create dummy trade so closed count > 0
        t = Trade(symbol="EXC1", side="sell", total=100, pnl=30.0, mode=mode, status="closed")
        db.add(t)
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.avg_mfe_pct == 30.0  # (40 + 20) / 2
        assert card.avg_mae_pct == -10.0  # (-5 + -15) / 2
        print("[PASS] Test 6: MFE & MAE excursion averages verified.")
    finally:
        db.close()


def test_07_profit_capture_ratio():
    """
    Verifies Profit Capture Ratio (PCR = Realized PnL Pct / MFE Pct).
    """
    db = _get_db()
    try:
        mode = f"P5_PCR_{uuid.uuid4().hex[:6]}"
        t = Trade(symbol="PCR_SYM", side="sell", total=100, price=1.30, market_price=1.00, pnl=30.0, mode=mode, status="closed")
        db.add(t)
        db.commit()

        journal = TradeEvaluator.evaluate_and_record_trade(trade=t, db=db, mfe_pct=40.0, mae_pct=-2.0)
        assert journal.profit_capture_ratio == 0.75
        assert journal.final_realized_pnl_usd == 30.0
        print("[PASS] Test 7: Profit Capture Ratio verified (PCR = 0.75 / 75%).")
    finally:
        db.close()


def test_08_entry_and_exit_efficiency():
    """
    Verifies Entry Efficiency (MFE / (MFE + |MAE|)) and Exit Efficiency (PCR * 100%).
    """
    db = _get_db()
    try:
        mode = f"P5_EFF_{uuid.uuid4().hex[:6]}"
        j = DecisionJournal(symbol="EFF1", mode=mode, mfe_pct=30.0, mae_pct=-10.0, profit_capture_ratio=0.60, final_realized_pnl_usd=18.0)
        t = Trade(symbol="EFF1", side="sell", total=100, pnl=18.0, mode=mode, status="closed")
        db.add_all([j, t])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.entry_efficiency == 75.0
        assert card.exit_efficiency == 60.0
        print("[PASS] Test 8: Entry and Exit Efficiency verified.")
    finally:
        db.close()


def test_09_false_positive_rate():
    """
    Verifies False Positive Rate on approved high-score entries that failed.
    """
    db = _get_db()
    try:
        mode = f"P5_FPR_{uuid.uuid4().hex[:6]}"
        j1 = DecisionJournal(symbol="FPR1", mode=mode, entry_score=85.0, final_realized_pnl_usd=50.0)
        j2 = DecisionJournal(symbol="FPR2", mode=mode, entry_score=78.0, final_realized_pnl_usd=20.0)
        j3 = DecisionJournal(symbol="FPR3", mode=mode, entry_score=72.0, final_realized_pnl_usd=-15.0)
        t = Trade(symbol="FPR1", side="sell", total=100, pnl=50.0, mode=mode, status="closed")
        db.add_all([j1, j2, j3, t])
        db.commit()

        card = TradeEvaluator.calculate_scorecard(db=db, mode=mode)
        assert card.false_positive_rate == 33.33
        print("[PASS] Test 9: False Positive Rate calculated accurately (33.33%).")
    finally:
        db.close()


def test_10_decision_journal_generation():
    """
    Verifies that TradeEvaluator generates complete DecisionJournal records linked to Trade.
    """
    db = _get_db()
    try:
        mode = f"P5_GEN_{uuid.uuid4().hex[:6]}"
        t = Trade(symbol="GEN_SYM", side="sell", total=50, price=2.0, market_price=1.6, pnl=10.0, mode=mode, status="closed")
        db.add(t)
        db.commit()

        j = TradeEvaluator.evaluate_and_record_trade(trade=t, db=db, exit_reason="TAKE_PROFIT_TRIGGER")
        assert j.id is not None
        assert j.trade_id == t.id
        assert j.symbol == "GEN_SYM"
        assert j.exit_reason == "TAKE_PROFIT_TRIGGER"
        assert j.final_realized_pnl_usd == 10.0
        print("[PASS] Test 10: DecisionJournal entry generated & persisted.")
    finally:
        db.close()


def test_11_post_mortem_synthesis():
    """
    Verifies that Post-Mortem text accurately synthesizes trading performance and lessons learned.
    """
    db = _get_db()
    try:
        mode = f"P5_SYN_{uuid.uuid4().hex[:6]}"
        t_win = Trade(symbol="SYN_WIN", side="sell", total=100, pnl=45.0, mode=mode, status="closed")
        t_loss = Trade(symbol="SYN_LOSS", side="sell", total=100, pnl=-18.0, mode=mode, status="closed")
        db.add_all([t_win, t_loss])
        db.commit()

        j_win = TradeEvaluator.evaluate_and_record_trade(trade=t_win, db=db, mfe_pct=50.0, mae_pct=-2.0, exit_reason="TRAILING_STOP")
        j_loss = TradeEvaluator.evaluate_and_record_trade(trade=t_loss, db=db, mfe_pct=2.0, mae_pct=-18.0, exit_reason="HARD_SL")

        assert "SYN_WIN" in j_win.ai_post_mortem
        assert "$+45.00" in j_win.ai_post_mortem
        assert "TRAILING_STOP" in j_win.ai_post_mortem
        assert "SYN_LOSS" in j_loss.ai_post_mortem
        assert "$-18.00" in j_loss.ai_post_mortem
        assert "HARD_SL" in j_loss.ai_post_mortem
        print("[PASS] Test 11: Post-Mortem learning diagnostic synthesized correctly.")
    finally:
        db.close()


def test_12_walk_forward_parameter_optimization():
    """
    Verifies walk-forward simulation runs in-sample training and out-of-sample testing.
    """
    trades = [
        Trade(symbol=f"OPT_{i}", side="sell", total=100, pnl=30.0 if i % 2 == 0 else -10.0, status="closed")
        for i in range(10)
    ]
    res = ParameterOptimizer.run_walk_forward_optimization(trades=trades, train_test_split=0.70)
    assert res.strategy_version.startswith("2.1-optimized")
    assert res.parameter_set is not None
    assert "take_profit_pct" in res.parameter_set
    assert res.in_sample_metrics["trades"] == 7
    assert res.out_of_sample_metrics["trades"] == 3
    print("[PASS] Test 12: Walk-forward optimization simulated on in-sample and out-of-sample splits.")


def test_13_non_autonomous_safety_invariant():
    """
    PRD Invariant: Optimization outputs cannot autonomously modify production rules.
    Must require human verification and approval.
    """
    trades = [Trade(symbol="SAFETY", side="sell", total=100, pnl=50.0, status="closed")]
    res = ParameterOptimizer.run_walk_forward_optimization(trades=trades)
    assert res.requires_manual_approval is True
    assert res.approved_by_human is False
    assert res.status == "INSUFFICIENT_DATA_FOR_OPTIMIZATION" or res.status == "RECOMMENDED_PENDING_APPROVAL"
    print("[PASS] Test 13: Non-autonomous invariant verified (human approval required).")


def test_14_market_regime_segmentation():
    """
    Verifies closed trade outcomes segmented across trending, ranging, and choppy regimes.
    """
    db = _get_db()
    try:
        mode = f"P5_REGIMES_{uuid.uuid4().hex[:6]}"
        j_trend = DecisionJournal(symbol="TR1", mode=mode, mfe_pct=45.0, final_realized_pnl_usd=35.0)
        j_range = DecisionJournal(symbol="RA1", mode=mode, mfe_pct=18.0, final_realized_pnl_usd=12.0)
        j_chop = DecisionJournal(symbol="CH1", mode=mode, mfe_pct=4.0, final_realized_pnl_usd=-10.0)
        db.add_all([j_trend, j_range, j_chop])
        db.commit()

        regimes = ParameterOptimizer.segment_by_market_regime(db=db, mode=mode)
        assert regimes["trending"]["trades"] == 1
        assert regimes["trending"]["winrate_pct"] == 100.0
        assert regimes["ranging"]["trades"] == 1
        assert regimes["ranging"]["winrate_pct"] == 100.0
        assert regimes["choppy"]["trades"] == 1
        assert regimes["choppy"]["winrate_pct"] == 0.0
        print("[PASS] Test 14: Market regime segmentation verified (Trending, Ranging, Choppy).")
    finally:
        db.close()


def test_15_fastapi_rest_endpoints():
    """
    Verifies that FastAPI endpoints for /api/v2/feedback/* and /api/v2/analytics/journal are operational.
    """
    # 1. Metrics endpoint
    r1 = client.get("/api/v2/feedback/metrics?mode=PAPER")
    assert r1.status_code == 200
    data1 = r1.json()
    assert "total_closed_trades" in data1
    assert "win_rate_pct" in data1
    assert "profit_factor" in data1
    assert "expectancy_usd" in data1

    # 2. Journal endpoint
    r2 = client.get("/api/v2/feedback/journal?limit=5")
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)

    # 3. Analytics journal alias
    r3 = client.get("/api/v2/analytics/journal?limit=5")
    assert r3.status_code == 200
    assert isinstance(r3.json(), list)

    # 4. Regimes endpoint
    r4 = client.get("/api/v2/feedback/regimes?mode=PAPER")
    assert r4.status_code == 200
    data4 = r4.json()
    assert "trending" in data4
    assert "ranging" in data4
    assert "choppy" in data4

    # 5. Optimization endpoint
    r5 = client.post("/api/v2/feedback/optimize?mode=PAPER")
    assert r5.status_code == 200
    data5 = r5.json()
    assert data5["requires_manual_approval"] is True
    assert data5["approved_by_human"] is False
    print("[PASS] Test 15: All 5 FastAPI Feedback REST endpoints verified.")


def run_all_tests():
    tests = [
        test_01_zero_dummy_data_empty_state,
        test_02_winrate_and_pnl_calculation,
        test_03_profit_factor_calculation,
        test_04_expectancy_calculation,
        test_05_max_drawdown_peak_to_trough,
        test_06_mfe_and_mae_metrics,
        test_07_profit_capture_ratio,
        test_08_entry_and_exit_efficiency,
        test_09_false_positive_rate,
        test_10_decision_journal_generation,
        test_11_post_mortem_synthesis,
        test_12_walk_forward_parameter_optimization,
        test_13_non_autonomous_safety_invariant,
        test_14_market_regime_segmentation,
        test_15_fastapi_rest_endpoints,
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
    print(f"RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed / len(tests) * 100:.1f}%)")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
