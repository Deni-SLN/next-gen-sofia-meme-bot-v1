"""
Test Suite for SOFIA MEME BOT V2 — Phase 6 Lifecycle Identity Audit (CEO Directive Section 2).

Verifies:
1. Two different mint addresses with the same symbol (collision prevention).
2. Multiple lifecycles for the same mint.
3. Concurrent positions in separate strategies.
4. Reopened positions after complete closure.
5. Partial exits followed by final closure.
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add api directory to sys.path
api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, init_db
from app.db.models import Trade
from app.v2.feedback.lifecycle_aggregator import LifecycleAggregator, PositionLifecycle

init_db()


def _get_db():
    return SessionLocal()


def test_01_two_different_mints_same_symbol():
    """
    Test 1: Two different mint addresses with the exact same ticker symbol (e.g. 'PEPE').
    Must NOT collide and must create 2 independent lifecycles.
    """
    db = _get_db()
    try:
        mode = f"TEST_MINT_COL_{uuid.uuid4().hex[:6]}"
        sym = "PEPE"
        mint_a = "MintPepeAlpha111111111111111111111111111111"
        mint_b = "MintPepeBeta222222222222222222222222222222"
        now = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Token A: Buy and Sell
        b_a = Trade(symbol=sym, side="buy", quantity=100.0, price=1.0, total=100.0, mode=mode, status="closed", opened_at=now, notes=f"[trending] [mint:{mint_a}]")
        s_a = Trade(symbol=sym, side="sell", quantity=100.0, price=1.2, total=120.0, mode=mode, status="closed", opened_at=now + timedelta(minutes=10), notes=f"[trending] [mint:{mint_a}] FULL_EXIT")

        # Token B: Buy and Sell at same time
        b_b = Trade(symbol=sym, side="buy", quantity=500.0, price=0.1, total=50.0, mode=mode, status="closed", opened_at=now + timedelta(minutes=1), notes=f"[ranging] [mint:{mint_b}]")
        s_b = Trade(symbol=sym, side="sell", quantity=500.0, price=0.08, total=40.0, mode=mode, status="closed", opened_at=now + timedelta(minutes=15), notes=f"[ranging] [mint:{mint_b}] FULL_EXIT")

        db.add_all([b_a, s_a, b_b, s_b])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lcs) == 2, f"Expected 2 separate lifecycles, got {len(lcs)}"

        lcs_by_mint = {lc.mint: lc for lc in lcs}
        assert mint_a in lcs_by_mint and mint_b in lcs_by_mint, "Both mints must be present"

        lc_a = lcs_by_mint[mint_a]
        lc_b = lcs_by_mint[mint_b]

        assert lc_a.symbol == "PEPE" and lc_b.symbol == "PEPE"
        assert lc_a.entry_quantity == 100.0 and lc_a.is_win is True
        assert lc_b.entry_quantity == 500.0 and lc_b.is_win is False
        assert lc_a.position_id != lc_b.position_id
        print("[PASS] Test 1: Two different mint addresses with identical symbol verified (Zero Collision).")
    finally:
        db.close()


def test_02_multiple_lifecycles_same_mint():
    """
    Test 2: Multiple lifecycles for the exact same mint across successive trading cycles.
    """
    db = _get_db()
    try:
        mode = f"TEST_MULTI_LC_{uuid.uuid4().hex[:6]}"
        mint = "MintBonkSuccessive33333333333333333333333333"
        sym = "BONK"
        t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Cycle 1
        b1 = Trade(symbol=sym, side="buy", quantity=100.0, price=1.0, total=100.0, mode=mode, status="closed", opened_at=t0, notes=f"[mint:{mint}]")
        s1 = Trade(symbol=sym, side="sell", quantity=100.0, price=1.2, total=120.0, mode=mode, status="closed", opened_at=t0 + timedelta(minutes=15), notes=f"[mint:{mint}] FULL_EXIT")

        # Cycle 2
        t1 = t0 + timedelta(hours=2)
        b2 = Trade(symbol=sym, side="buy", quantity=150.0, price=1.1, total=165.0, mode=mode, status="closed", opened_at=t1, notes=f"[mint:{mint}]")
        s2 = Trade(symbol=sym, side="sell", quantity=150.0, price=1.3, total=195.0, mode=mode, status="closed", opened_at=t1 + timedelta(minutes=20), notes=f"[mint:{mint}] FULL_EXIT")

        db.add_all([b1, s1, b2, s2])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lcs) == 2, f"Expected 2 separate lifecycles for same mint, got {len(lcs)}"
        assert lcs[0].position_id != lcs[1].position_id
        assert lcs[0].entry_quantity == 100.0
        assert lcs[1].entry_quantity == 150.0
        print("[PASS] Test 2: Multiple lifecycles for same mint verified.")
    finally:
        db.close()


def test_03_concurrent_positions_separate_strategies():
    """
    Test 3: Concurrent positions in separate strategies for the same mint.
    Strategy A, B, and C must never cross-pollinate or share lifecycles.
    """
    db = _get_db()
    try:
        mint = "MintSharedCandidate444444444444444444444444"
        sym = "SHARED_MINT"
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        mode_a = f"TEST_SA_{uuid.uuid4().hex[:4]}"
        mode_b = f"TEST_SB_{uuid.uuid4().hex[:4]}"
        mode_c = f"TEST_SC_{uuid.uuid4().hex[:4]}"

        # Strategy A Trade
        ba = Trade(symbol=sym, side="buy", quantity=50, price=1.0, total=50, mode=mode_a, status="closed", opened_at=t0, notes=f"[mint:{mint}]")
        sa = Trade(symbol=sym, side="sell", quantity=50, price=1.25, total=62.5, mode=mode_a, status="closed", opened_at=t0 + timedelta(minutes=10), notes=f"[mint:{mint}] FULL")

        # Strategy B Trade
        bb = Trade(symbol=sym, side="buy", quantity=100, price=1.0, total=100, mode=mode_b, status="closed", opened_at=t0, notes=f"[mint:{mint}]")
        sb = Trade(symbol=sym, side="sell", quantity=100, price=1.20, total=120, mode=mode_b, status="closed", opened_at=t0 + timedelta(minutes=12), notes=f"[mint:{mint}] FULL")

        # Strategy C Trade
        bc = Trade(symbol=sym, side="buy", quantity=200, price=1.0, total=200, mode=mode_c, status="closed", opened_at=t0, notes=f"[mint:{mint}]")
        sc = Trade(symbol=sym, side="sell", quantity=200, price=1.35, total=270, mode=mode_c, status="closed", opened_at=t0 + timedelta(minutes=15), notes=f"[mint:{mint}] FULL")

        db.add_all([ba, sa, bb, sb, bc, sc])
        db.commit()

        lcs_a = LifecycleAggregator.aggregate_lifecycles(db, mode=mode_a)
        lcs_b = LifecycleAggregator.aggregate_lifecycles(db, mode=mode_b)
        lcs_c = LifecycleAggregator.aggregate_lifecycles(db, mode=mode_c)

        assert len(lcs_a) == 1 and lcs_a[0].entry_quantity == 50
        assert len(lcs_b) == 1 and lcs_b[0].entry_quantity == 100
        assert len(lcs_c) == 1 and lcs_c[0].entry_quantity == 200

        assert lcs_a[0].strategy_id == f"STRAT_{mode_a}"
        assert lcs_b[0].strategy_id == f"STRAT_{mode_b}"
        assert lcs_c[0].strategy_id == f"STRAT_{mode_c}"
        print("[PASS] Test 3: Concurrent positions across separate strategies verified.")
    finally:
        db.close()


def test_04_reopened_positions_after_complete_closure():
    """
    Test 4: Reopened position after full closure creates distinct position_id and resets state.
    """
    db = _get_db()
    try:
        mode = f"TEST_REOPEN_{uuid.uuid4().hex[:6]}"
        mint = "MintReopenCoin55555555555555555555555555555"
        sym = "REOPEN"
        t0 = datetime(2026, 10, 1, 14, 0, 0, tzinfo=timezone.utc)

        b1 = Trade(symbol=sym, side="buy", quantity=100.0, price=2.0, total=200.0, mode=mode, status="closed", opened_at=t0, notes=f"[mint:{mint}]")
        s1 = Trade(symbol=sym, side="sell", quantity=100.0, price=2.2, total=220.0, mode=mode, status="closed", opened_at=t0 + timedelta(minutes=5), notes=f"[mint:{mint}] 100_FULL")

        t1 = t0 + timedelta(days=1)
        b2 = Trade(symbol=sym, side="buy", quantity=100.0, price=1.8, total=180.0, mode=mode, status="closed", opened_at=t1, notes=f"[mint:{mint}]")
        s2 = Trade(symbol=sym, side="sell", quantity=100.0, price=1.6, total=160.0, mode=mode, status="closed", opened_at=t1 + timedelta(minutes=8), notes=f"[mint:{mint}] FULL_STOP")

        db.add_all([b1, s1, b2, s2])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lcs) == 2
        assert lcs[0].status == "CLOSED" and lcs[1].status == "CLOSED"
        assert lcs[0].position_id != lcs[1].position_id
        assert lcs[0].is_win is True and lcs[1].is_win is False
        print("[PASS] Test 4: Reopened positions after complete closure verified.")
    finally:
        db.close()


def test_05_partial_exits_followed_by_final_closure():
    """
    Test 5: Partial exits (e.g. 25%, 50%) followed by final closure leg (trailing stop).
    Unrealized capital tracked during open phase, aggregated into 1 completed lifecycle upon full closure.
    """
    db = _get_db()
    try:
        mode = f"TEST_PAR_FULL_{uuid.uuid4().hex[:6]}"
        mint = "MintPartialLadder666666666666666666666666666"
        sym = "LADDER"
        t0 = datetime(2026, 10, 1, 16, 0, 0, tzinfo=timezone.utc)

        # Entry: 100 tokens at $1.00 ($100 total)
        b = Trade(symbol=sym, side="buy", quantity=100.0, price=1.0, total=100.0, mode=mode, status="open", opened_at=t0, notes=f"[mint:{mint}]")
        # Leg 1: Sell 30 tokens at $1.20 ($36 proceeds)
        s1 = Trade(symbol=sym, side="sell", quantity=30.0, price=1.2, total=36.0, mode=mode, status="open", opened_at=t0 + timedelta(minutes=5), notes=f"[mint:{mint}] PARTIAL_30")
        # Leg 2: Sell 40 tokens at $1.40 ($56 proceeds)
        s2 = Trade(symbol=sym, side="sell", quantity=40.0, price=1.4, total=56.0, mode=mode, status="open", opened_at=t0 + timedelta(minutes=10), notes=f"[mint:{mint}] PARTIAL_40")
        # Leg 3: Sell remaining 30 tokens at $1.15 ($34.5 proceeds) - Final full exit
        s3 = Trade(symbol=sym, side="sell", quantity=30.0, price=1.15, total=34.5, mode=mode, status="closed", opened_at=t0 + timedelta(minutes=20), notes=f"[mint:{mint}] TRAILING_STOP_FULL")

        db.add_all([b, s1, s2, s3])
        db.commit()

        lcs = LifecycleAggregator.aggregate_lifecycles(db, mode=mode)
        assert len(lcs) == 1
        lc = lcs[0]
        assert lc.status == "CLOSED"
        assert lc.entry_quantity == 100.0
        assert lc.remaining_quantity == 0.0
        assert lc.partial_exits_count == 3
        assert len(lc.exit_trades) == 3
        # Total proceeds: 36 + 56 + 34.5 = 126.5
        assert round(lc.total_exit_proceeds_usd, 2) == 126.50
        assert round(lc.net_pnl_usd, 2) == round(126.50 - 100.0 - lc.total_execution_costs_usd, 2)
        assert len(lc.execution_ids) == 4  # 1 entry + 3 exits
        print("[PASS] Test 5: Partial exits followed by final closure verified.")
    finally:
        db.close()


def run_all_tests():
    tests = [
        test_01_two_different_mints_same_symbol,
        test_02_multiple_lifecycles_same_mint,
        test_03_concurrent_positions_separate_strategies,
        test_04_reopened_positions_after_complete_closure,
        test_05_partial_exits_followed_by_final_closure,
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
    print(f"LIFECYCLE IDENTITY AUDIT RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed / len(tests) * 100:.1f}%)")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
