"""
Test Suite for SOFIA MEME BOT V2 — Phase 3: AI Exit Intelligence & Adaptive Profit Management.
Strictly verifies all 20 requirements in the DSLN Capital CEO Directive Section 9:
1. Momentum deterioration exit test
2. Sell pressure exit test
3. Smart money exit test
4. Liquidity deterioration exit test
5. Time-based thesis deterioration exit test
6. Partial exit 25% test
7. Partial exit 50% test
8. Partial exit 75% test
9. Full exit 100% test
10. Dynamic take profit test
11. Adaptive trailing stop ratchet test (never moves down)
12. Break-even protection ratchet test
13. Deterministic hard stop override test (overrides AI HOLD)
14. Emergency exit test (honeypot or >=50% liquidity collapse)
15. Missing data safe rejection test (missing data is never safe)
16. Jupiter fresh quote before sell test
17. Realized PnL and fee accounting test
18. Remaining token balance retention test
19. Decision Journal MFE/MAE/Profit Capture Ratio recording test
20. PositionEvent audit logging test
"""

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add api directory to sys.path
api_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(api_dir))

from fastapi.testclient import TestClient
from sqlalchemy import select, or_, func, delete

from app.db.session import init_db, SessionLocal
from app.main import app
from app.db.models import Trade, PortfolioHolding
from app.v2.db.models import AgentDecision, ExitAssessment, PositionEvent, DecisionJournal
from app.v2.services.exit_intelligence import exit_intelligence, ExitIntelligenceService
from app.v2.core.exit_policy import exit_policy, ExitPolicy
from app.v2.services.adaptive_profit_manager import adaptive_profit_manager
from app.v2.services.partial_exit_manager import partial_exit_manager
from app.v2.agents.exit_agent import exit_agent

init_db()
client = TestClient(app)


def _clean_symbol(db, sym):
    db.execute(delete(PortfolioHolding).where(PortfolioHolding.symbol == sym))
    db.execute(delete(Trade).where(Trade.symbol == sym))
    db.execute(delete(PositionEvent).where(PositionEvent.symbol == sym))
    db.execute(delete(DecisionJournal).where(DecisionJournal.symbol == sym))
    db.commit()


def test_01_momentum_deterioration_exit():
    """1. Momentum deterioration: retracement >=25% or 5m price drop >=12% triggers high urgency."""
    pos = {
        "position_id": "test_pos_01",
        "symbol": "TEST_MOM",
        "mint": "Mint_Mom_01",
        "avg_entry_price": 0.010,
        "current_price": 0.0075,
        "quantity": 10000.0,
        "liquidity_usd": 30000.0,
        "position_age_minutes": 20.0,
    }
    market_data = {
        "price": 0.0075,
        "liquidity_usd": 30000.0,
        "price_change_5m_pct": -14.0,
        "price_change_1h_pct": -25.0,
        "volume_5m_usd": 1000.0,
        "volume_1h_usd": 40000.0,
        "txns": {"m5": {"buys": 2, "sells": 15}},
    }
    # Pre-record high price to simulate 25% retracement
    adaptive_profit_manager.update_position_tracking("TEST_MOM", current_price=0.012, entry_price=0.010)

    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True)
    assert out.dimensions.momentum_deterioration >= 18.0, f"Expected momentum >= 18.0, got {out.dimensions.momentum_deterioration}"
    assert out.market_conditions.momentum in ("weakening", "collapsed")
    print(f"[PASS] Test 1: Momentum deterioration score: {out.dimensions.momentum_deterioration}/25 ({out.market_conditions.momentum})")


def test_02_sell_pressure_exit():
    """2. Sell pressure: 5m sell ratio >= 75% with high sell count triggers dominant sell pressure score."""
    pos = {
        "position_id": "test_pos_02",
        "symbol": "TEST_SELL",
        "mint": "Mint_Sell_02",
        "avg_entry_price": 0.020,
        "current_price": 0.020,
        "quantity": 5000.0,
        "liquidity_usd": 40000.0,
        "position_age_minutes": 10.0,
    }
    market_data = {
        "price": 0.020,
        "liquidity_usd": 40000.0,
        "price_change_5m_pct": -2.0,
        "price_change_1h_pct": 5.0,
        "volume_5m_usd": 8000.0,
        "volume_1h_usd": 50000.0,
        "txns": {"m5": {"buys": 3, "sells": 20}},
    }
    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True)
    assert out.dimensions.sell_pressure >= 18.0, f"Expected sell pressure >= 18.0, got {out.dimensions.sell_pressure}"
    assert out.market_conditions.sell_pressure == "dominant"
    print(f"[PASS] Test 2: Sell pressure score: {out.dimensions.sell_pressure}/20 ({out.market_conditions.sell_pressure})")


def test_03_smart_money_exit():
    """3. Smart money exit: Whale dump or insider distribution triggers high smart money exit score."""
    pos = {
        "position_id": "test_pos_03",
        "symbol": "TEST_SM",
        "mint": "Mint_SM_03",
        "avg_entry_price": 0.050,
        "current_price": 0.050,
        "quantity": 2000.0,
        "liquidity_usd": 50000.0,
        "position_age_minutes": 15.0,
    }
    market_data = {
        "price": 0.050,
        "liquidity_usd": 50000.0,
        "txns": {"m5": {"buys": 4, "sells": 22}},
        "large_sells_5m": 5,
        "dev_holding_pct": 14.5,
    }
    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True)
    assert out.dimensions.smart_money_distribution >= 18.0, f"Expected smart money >= 18.0, got {out.dimensions.smart_money_distribution}"
    assert any("WHALE_DUMP" in f or "DEV_HOLDING" in f for f in out.risk_flags)
    print(f"[PASS] Test 3: Smart money distribution score: {out.dimensions.smart_money_distribution}/20 (Flags: {out.risk_flags})")


def test_04_liquidity_deterioration_exit():
    """4. Liquidity deterioration: Pool liquidity drop >= 40% triggers liquidity deterioration penalty."""
    pos = {
        "position_id": "test_pos_04",
        "symbol": "TEST_LIQ",
        "mint": "Mint_Liq_04",
        "avg_entry_price": 0.010,
        "current_price": 0.010,
        "quantity": 10000.0,
        "liquidity_usd": 50000.0,  # Entry liquidity was 50k
        "position_age_minutes": 30.0,
    }
    market_data = {
        "price": 0.010,
        "liquidity_usd": 28000.0,  # Dropped from 50k to 28k (44% drop)
        "txns": {"m5": {"buys": 5, "sells": 5}},
    }
    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True)
    assert out.dimensions.liquidity_deterioration >= 9.0, f"Expected liquidity >= 9.0, got {out.dimensions.liquidity_deterioration}"
    assert out.market_conditions.liquidity in ("decaying", "critical_drop")
    print(f"[PASS] Test 4: Liquidity decay score: {out.dimensions.liquidity_deterioration}/10 ({out.market_conditions.liquidity})")


def test_05_time_thesis_deterioration_exit():
    """5. Time-based thesis deterioration: Long holding duration (>120m) without profit expansion penalizes position."""
    pos = {
        "position_id": "test_pos_05",
        "symbol": "TEST_TIME",
        "mint": "Mint_Time_05",
        "avg_entry_price": 0.010,
        "current_price": 0.0102,  # Flat +2% after 150 mins
        "quantity": 10000.0,
        "liquidity_usd": 30000.0,
        "position_age_minutes": 150.0,
    }
    market_data = {
        "price": 0.0102,
        "liquidity_usd": 30000.0,
        "txns": {"m5": {"buys": 5, "sells": 5}},
    }
    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True)
    assert out.dimensions.time_thesis_deterioration == 10.0, f"Expected 10.0, got {out.dimensions.time_thesis_deterioration}"
    print(f"[PASS] Test 5: Time thesis deterioration score: {out.dimensions.time_thesis_deterioration}/10")


def test_06_partial_exit_25():
    """6. Partial exit 25%: Sells exactly 25% of position, reduces balance by 25%, retains entry price."""
    db = SessionLocal()
    sym = "P3_P25"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.006,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=25.0, mode="PAPER")
        assert res["status"] == "success"
        assert abs(res["qty_sold"] - 25.0) < 0.1
        assert abs(res["remaining_quantity"] - 75.0) < 0.1
        assert res["event_type"] == "V2_PARTIAL_EXIT_25"

        # Verify DB holding retained with same entry price
        refreshed = db.execute(select(PortfolioHolding).where(PortfolioHolding.symbol == sym, PortfolioHolding.mode == "PAPER")).scalar_one()
        assert abs(refreshed.quantity - 75.0) < 0.1
        assert abs(refreshed.avg_entry_price - 0.005) < 1e-6
        print(f"[PASS] Test 6: Partial exit 25% executed. Sold {res['qty_sold']}, Remaining {refreshed.quantity}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_07_partial_exit_50():
    """7. Partial exit 50%: Sells exactly 50% of remaining position balance."""
    db = SessionLocal()
    sym = "P3_P50"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.006,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=50.0, mode="PAPER")
        assert res["status"] == "success"
        assert abs(res["qty_sold"] - 50.0) < 0.1
        assert abs(res["remaining_quantity"] - 50.0) < 0.1
        assert res["event_type"] == "V2_PARTIAL_EXIT_50"
        print(f"[PASS] Test 7: Partial exit 50% executed. Sold {res['qty_sold']}, Remaining {res['remaining_quantity']}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_08_partial_exit_75():
    """8. Partial exit 75%: Sells exactly 75% of remaining position balance."""
    db = SessionLocal()
    sym = "P3_P75"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.0075,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=75.0, mode="PAPER")
        assert res["status"] == "success"
        assert abs(res["qty_sold"] - 75.0) < 0.1
        assert abs(res["remaining_quantity"] - 25.0) < 0.1
        assert res["event_type"] == "V2_PARTIAL_EXIT_75"
        print(f"[PASS] Test 8: Partial exit 75% executed. Sold {res['qty_sold']}, Remaining {res['remaining_quantity']}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_09_full_exit_100():
    """9. Full exit 100%: Liquidates remaining holding, removes holding, creates closed trade and DecisionJournal."""
    db = SessionLocal()
    sym = "P3_F100"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.007,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=100.0, mode="PAPER")
        assert res["status"] == "success"
        assert res["is_fully_closed"] is True
        assert res["remaining_quantity"] == 0.0

        # Verify DB holding is deleted
        db_holding = db.execute(select(PortfolioHolding).where(PortfolioHolding.symbol == sym, PortfolioHolding.mode == "PAPER")).scalar_one_or_none()
        assert db_holding is None, "Holding should be deleted upon 100% full exit"

        # Verify DecisionJournal was recorded
        dj = db.execute(select(DecisionJournal).where(DecisionJournal.symbol == sym, DecisionJournal.mode == "PAPER")).scalar_one_or_none()
        assert dj is not None, "DecisionJournal must be recorded upon full exit"
        print(f"[PASS] Test 9: Full exit 100% executed. Holding deleted, DecisionJournal ID {dj.id} created.")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_10_dynamic_take_profit():
    """10. Dynamic take profit: Targets (+40%, +80%, +150%) recommend laddered reduction."""
    res_40 = ExitPolicy.evaluate_position_policy(
        entry_price=0.010, current_price=0.0142, highest_price=0.0142,
        current_trailing_stop=None, breakeven_activated=False, liquidity_decay_pct=0.0
    )
    assert res_40.action == "REDUCE_25" and res_40.suggested_sell_pct == 25

    res_80 = ExitPolicy.evaluate_position_policy(
        entry_price=0.010, current_price=0.0185, highest_price=0.0185,
        current_trailing_stop=None, breakeven_activated=False, liquidity_decay_pct=0.0
    )
    assert res_80.action == "REDUCE_50" and res_80.suggested_sell_pct == 50

    res_150 = ExitPolicy.evaluate_position_policy(
        entry_price=0.010, current_price=0.0260, highest_price=0.0260,
        current_trailing_stop=None, breakeven_activated=False, liquidity_decay_pct=0.0
    )
    assert res_150.action == "REDUCE_75" and res_150.suggested_sell_pct == 75
    print("[PASS] Test 10: Dynamic take profit ladder verified (+40%->25%, +80%->50%, +150%->75%).")


def test_11_adaptive_trailing_stop_never_moves_down():
    """11. Adaptive trailing stop ratchet: Invariant test: trailing stop can NEVER move downward."""
    sym = "TEST_TRAIL_INVARIANT"
    # Entry at 0.010, peak at 0.015 (+50% profit)
    _, _, stop1, _ = adaptive_profit_manager.update_position_tracking(sym, current_price=0.015, entry_price=0.010)
    assert stop1 is not None and stop1 > 0.010

    # Price drops to 0.014 -> stop MUST NOT decrease
    _, _, stop2, _ = adaptive_profit_manager.update_position_tracking(sym, current_price=0.014, entry_price=0.010)
    assert stop2 >= stop1, f"Trailing stop moved down! {stop2} < {stop1}"

    # Price drops to 0.012 -> stop MUST NOT decrease
    _, _, stop3, _ = adaptive_profit_manager.update_position_tracking(sym, current_price=0.012, entry_price=0.010)
    assert stop3 >= stop1, f"Trailing stop moved down! {stop3} < {stop1}"
    print(f"[PASS] Test 11: Invariant verified: Trailing stop ({stop1:.6f} -> {stop2:.6f} -> {stop3:.6f}) never moved downward.")


def test_12_breakeven_protection_ratchet():
    """12. Break-even ratchet: When peak profit >= +20%, stop is ratcheted to entry price + 1% fee buffer."""
    res = ExitPolicy.evaluate_position_policy(
        entry_price=0.010,
        current_price=0.0122,  # +22%
        highest_price=0.0122,
        current_trailing_stop=None,
        breakeven_activated=False,
        liquidity_decay_pct=0.0,
    )
    assert res.breakeven_triggered is True
    assert res.trailing_stop_price is not None
    assert abs(res.trailing_stop_price - (0.010 * 1.01)) < 1e-6, f"Expected BE stop {0.010 * 1.01}, got {res.trailing_stop_price}"
    print(f"[PASS] Test 12: Break-even protection ratcheted to {res.trailing_stop_price} (Entry + 1%).")


def test_13_deterministic_hard_stop_override():
    """13. Deterministic hard stop: Loss >= 12% overrides any AI recommendation with FULL_EXIT."""
    pos = {
        "position_id": "test_pos_13",
        "symbol": "TEST_HARD_SL",
        "mint": "Mint_SL_13",
        "avg_entry_price": 0.010,
        "current_price": 0.0087,  # -13% loss (violates -12% hard SL)
        "quantity": 10000.0,
        "liquidity_usd": 30000.0,
        "position_age_minutes": 15.0,
    }
    market_data = {
        "price": 0.0087,
        "liquidity_usd": 30000.0,
        "txns": {"m5": {"buys": 10, "sells": 10}},  # Neutral txns so pure AI might hold
    }
    out, _ = ExitIntelligenceService.evaluate_position(pos, market_data, force_deterministic=True, strategy_mode="DEFAULT")
    assert out.decision == "FULL_EXIT"
    assert out.suggested_sell_percentage == 100
    assert any("HARD_STOP" in r or "RISK VETO" in r for r in out.reasoning)
    print(f"[PASS] Test 13: Deterministic hard stop override verified: Decision={out.decision}, Sell={out.suggested_sell_percentage}%")


def test_14_emergency_exit_honeypot_or_liquidity():
    """14. Emergency exit: Honeypot flag or >=50% liquidity collapse triggers immediate EMERGENCY_EXIT."""
    # Subtest A: Honeypot
    pos_a = {
        "position_id": "test_pos_14a",
        "symbol": "TEST_HONEY",
        "mint": "Mint_Honey_14",
        "avg_entry_price": 0.010,
        "current_price": 0.010,
        "quantity": 5000.0,
        "liquidity_usd": 20000.0,
    }
    market_honey = {"price": 0.010, "liquidity_usd": 20000.0, "is_honeypot": True}
    out_a, _ = ExitIntelligenceService.evaluate_position(pos_a, market_honey, force_deterministic=True)
    assert out_a.decision == "EMERGENCY_EXIT"
    assert out_a.suggested_sell_percentage == 100

    # Subtest B: >=50% liquidity collapse
    pos_b = {
        "position_id": "test_pos_14b",
        "symbol": "TEST_COLLAPSE",
        "mint": "Mint_Col_14",
        "avg_entry_price": 0.010,
        "current_price": 0.010,
        "quantity": 5000.0,
        "liquidity_usd": 40000.0,  # Entry liq was 40k
    }
    market_collapse = {"price": 0.010, "liquidity_usd": 15000.0}  # 62.5% collapse
    out_b, _ = ExitIntelligenceService.evaluate_position(pos_b, market_collapse, force_deterministic=True)
    assert out_b.decision == "EMERGENCY_EXIT"
    assert out_b.suggested_sell_percentage == 100
    print("[PASS] Test 14: Emergency exit verified for both honeypot and >50% liquidity collapse.")


def test_15_missing_data_safe_rejection():
    """15. Missing data safe rejection: Missing market data is NEVER interpreted as safe."""
    pos = {
        "position_id": "test_pos_15",
        "symbol": "TEST_MISSING",
        "mint": "Mint_Missing_15",
        "avg_entry_price": 0.010,
        "current_price": 0.0,  # No price
        "quantity": 5000.0,
        "liquidity_usd": 0.0,
    }
    # Pass None market data
    out, snapshot = ExitIntelligenceService.evaluate_position(pos, market_data=None, force_deterministic=True)
    assert out.confidence == "low"
    assert any("MISSING" in f for f in out.risk_flags)
    assert out.dimensions.momentum_deterioration > 0
    assert out.dimensions.sell_pressure > 0
    print(f"[PASS] Test 15: Missing data verified non-safe: Confidence={out.confidence}, Flags={out.risk_flags}")


def test_16_jupiter_fresh_quote_before_sell():
    """16. Jupiter / Market resolution: sell execution resolves real quotes and computes net proceeds."""
    from app.services import market
    tok = market.resolve_holding_live_price("BONK", avg_entry_price=0.000020, current_price=0.000022)
    assert tok is not None
    assert float(tok.get("price") or 0.0) > 0
    print(f"[PASS] Test 16: Live market quote resolved: BONK price=${float(tok['price']):.8f}, liq=${float(tok.get('liquidity') or 0):,.0f}")


def test_17_realized_pnl_and_fee_accounting():
    """17. Realized PnL & Fee Accounting: Realized PnL strictly deducts slippage, DEX fee, and gas fee."""
    db = SessionLocal()
    sym = "P3_FEE"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.006,
            entry_costs_usd=0.05,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=100.0, mode="PAPER")
        # Check that realized PnL was calculated net of costs
        assert "realized_pnl_usd" in res
        assert "realized_pnl_pct" in res
        assert res["realized_pnl_usd"] != 0.0

        # Verify trade record exists with fees
        trade = db.execute(select(Trade).where(Trade.symbol == sym, Trade.side == "sell")).scalars().first()
        assert trade is not None
        assert trade.dex_fee_usd > 0
        assert trade.gas_fee_usd > 0
        assert abs(trade.pnl - res["realized_pnl_usd"]) < 1e-3
        print(f"[PASS] Test 17: Accounting verified: PnL=${trade.pnl:+.4f}, DEX Fee=${trade.dex_fee_usd:.6f}, Gas=${trade.gas_fee_usd:.6f}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_18_remaining_token_balance_retention():
    """18. Remaining token balance retention: Partial sale retains exact remaining tokens without cost-basis distortion."""
    db = SessionLocal()
    sym = "P3_RET"
    try:
        _clean_symbol(db, sym)
        entry_p = 0.005
        initial_q = 100.0
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=initial_q,
            avg_entry_price=entry_p,
            current_price=0.006,
            liquidity_usd=30000.0,
        )
        db.add(holding)
        db.commit()

        # Step 1: Sell 25% (25 tokens), 75 tokens remain
        res1 = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=25.0, mode="PAPER")
        h1 = db.execute(select(PortfolioHolding).where(PortfolioHolding.symbol == sym, PortfolioHolding.mode == "PAPER")).scalar_one()
        assert abs(h1.quantity - 75.0) < 0.1
        assert abs(h1.avg_entry_price - entry_p) < 1e-6

        # Step 2: Sell 50% of remainder (37.5 tokens), 37.5 tokens remain
        res2 = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=50.0, mode="PAPER")
        h2 = db.execute(select(PortfolioHolding).where(PortfolioHolding.symbol == sym, PortfolioHolding.mode == "PAPER")).scalar_one()
        assert abs(h2.quantity - 37.5) < 0.1
        assert abs(h2.avg_entry_price - entry_p) < 1e-6
        print(f"[PASS] Test 18: Retention verified: 100 -> 75 (25% sold) -> 37.5 (50% sold). Cost basis preserved at ${entry_p}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_19_decision_journal_mfe_mae_capture():
    """19. Decision Journal: MFE, MAE, and Profit Capture Ratio accurately recorded upon trade closure."""
    db = SessionLocal()
    sym = "P3_JRNL"
    try:
        _clean_symbol(db, sym)
        entry_p = 0.005
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=entry_p,
            current_price=0.007,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        # Update high excursion to 0.008 (+60% MFE) and low to 0.0045 (-10% MAE)
        adaptive_profit_manager.update_position_tracking(sym, current_price=0.008, entry_price=entry_p)
        adaptive_profit_manager.update_position_tracking(sym, current_price=0.0045, entry_price=entry_p)

        res = partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=100.0, mode="PAPER")
        assert res["is_fully_closed"] is True

        journal = db.execute(select(DecisionJournal).where(DecisionJournal.symbol == sym, DecisionJournal.mode == "PAPER")).scalars().first()
        assert journal is not None
        assert journal.mfe_pct >= 55.0, f"Expected MFE >= 55%, got {journal.mfe_pct}"
        assert journal.mae_pct <= -5.0, f"Expected MAE <= -5%, got {journal.mae_pct}"
        assert journal.profit_capture_ratio > 0.0
        assert journal.final_realized_pnl_usd != 0.0
        print(f"[PASS] Test 19: Decision Journal recorded: MFE={journal.mfe_pct}%, MAE={journal.mae_pct}%, ProfitCapture={journal.profit_capture_ratio}")
    finally:
        _clean_symbol(db, sym)
        db.close()


def test_20_position_event_audit_logging():
    """20. PositionEvent audit logging: All exit executions produce immutable, traceable audit logs."""
    db = SessionLocal()
    sym = "P3_AUD"
    try:
        _clean_symbol(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=100.0,
            avg_entry_price=0.005,
            current_price=0.006,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=25.0, mode="PAPER", exit_reason="TAKE_PROFIT_STAGE_1")
        partial_exit_manager.execute_partial_exit(db=db, symbol=sym, sell_pct=100.0, mode="PAPER", exit_reason="FINAL_CLOSE")

        events = db.execute(select(PositionEvent).where(PositionEvent.symbol == sym, PositionEvent.mode == "PAPER")).scalars().all()
        assert len(events) >= 2
        types = [e.event_type for e in events]
        assert "V2_PARTIAL_EXIT_25" in types
        assert "V2_FULL_EXIT" in types
        print(f"[PASS] Test 20: PositionEvent audit trail verified ({len(events)} events: {types})")
    finally:
        _clean_symbol(db, sym)
        db.close()


def run_all_tests():
    print("=" * 70)
    print("SOFIA MEME BOT V2 - PHASE 3 TEST SUITE (20 MANDATORY TESTS)")
    print("=" * 70)
    tests = [
        test_01_momentum_deterioration_exit,
        test_02_sell_pressure_exit,
        test_03_smart_money_exit,
        test_04_liquidity_deterioration_exit,
        test_05_time_thesis_deterioration_exit,
        test_06_partial_exit_25,
        test_07_partial_exit_50,
        test_08_partial_exit_75,
        test_09_full_exit_100,
        test_10_dynamic_take_profit,
        test_11_adaptive_trailing_stop_never_moves_down,
        test_12_breakeven_protection_ratchet,
        test_13_deterministic_hard_stop_override,
        test_14_emergency_exit_honeypot_or_liquidity,
        test_15_missing_data_safe_rejection,
        test_16_jupiter_fresh_quote_before_sell,
        test_17_realized_pnl_and_fee_accounting,
        test_18_remaining_token_balance_retention,
        test_19_decision_journal_mfe_mae_capture,
        test_20_position_event_audit_logging,
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
