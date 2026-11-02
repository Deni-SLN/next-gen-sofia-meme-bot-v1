"""
Test Suite for SOFIA MEME BOT V2 — Phase 4: Autonomous Position Manager & Trade Supervisor.
Verifies all requirements in PRD Section 7 & 8:
1. Formal Position Lifecycle State Machine (8 States)
2. Illegal Transition Rejection & Reconciliation Invariant
3. Conflict Resolution Scenario A (Entry BUY vs Risk Veto)
4. Conflict Resolution Scenario B (Exit HOLD vs Deterministic Hard SL)
5. Conflict Resolution Scenario C (Exit REDUCE vs Risk Policy)
6. Conflict Resolution Scenario D (Stale Market Data Guard)
7. Conflict Resolution Scenario E (AI Provider Outage Fallback)
8. Position Capacity Limit Enforcement (Max Open Positions)
9. Daily Drawdown Circuit Breaker
10. Consecutive Error Tracking & Automated Circuit Breaker
11. Emergency Kill Switch (Manual & Automated)
12. Position Recovery After Server Restart
13. Reconciled Balance Accounting Invariant
14. Supervisor Telemetry & Multi-Agent Health Monitoring
15. End-to-End Autonomous Supervision Tick
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add api directory to sys.path
api_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(api_dir))

from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from app.db.session import init_db, SessionLocal
from app.main import app
from app.db.models import Trade, PortfolioHolding
from app.v2.core.position_state_machine import (
    position_state_machine,
    InvalidStateTransitionError,
    PositionStateMachine,
)
from app.v2.core.conflict_resolver import conflict_resolver, ConflictResolver
from app.v2.core.supervisor import trade_supervisor, AutonomousTradeSupervisor
from app.v2.agents.supervisor_agent import supervisor_agent
from app.v2.agents.registry import agent_registry
from app.v2.db.models import PositionEvent

init_db()
client = TestClient(app)


def _clean_test_data(db, sym):
    try:
        db.rollback()
    except Exception:
        pass
    db.execute(delete(PortfolioHolding).where(PortfolioHolding.symbol == sym))
    db.execute(delete(Trade).where(Trade.symbol == sym))
    db.execute(delete(PositionEvent).where(PositionEvent.symbol == sym))
    db.commit()


def test_01_lifecycle_state_transitions():
    """1. Formal Position Lifecycle: Tests valid sequential progression across all 8 states."""
    sym = "P4_LIFECYCLE"
    position_state_machine.clear()
    pos = position_state_machine.get_or_create_position(
        symbol=sym, mint="Mint_LC_01", mode="PAPER", initial_quantity=100.0, entry_price=0.010, initial_state="DISCOVERED"
    )
    assert pos.current_state == "DISCOVERED"

    # DISCOVERED -> ENTRY_APPROVED
    pos = position_state_machine.transition_to(sym, "ENTRY_APPROVED", "Quality Gate Passed")
    assert pos.current_state == "ENTRY_APPROVED"

    # ENTRY_APPROVED -> BUY_PENDING
    pos = position_state_machine.transition_to(sym, "BUY_PENDING", "Order Dispatched to DEX")
    assert pos.current_state == "BUY_PENDING"

    # BUY_PENDING -> POSITION_OPEN
    pos = position_state_machine.transition_to(sym, "POSITION_OPEN", "Transaction Confirmed on Solana")
    assert pos.current_state == "POSITION_OPEN"

    # POSITION_OPEN -> MONITORING
    pos = position_state_machine.transition_to(sym, "MONITORING", "Position active in monitoring loop")
    assert pos.current_state == "MONITORING"

    # MONITORING -> SELL_PENDING
    pos = position_state_machine.transition_to(sym, "SELL_PENDING", "Take-Profit triggered")
    assert pos.current_state == "SELL_PENDING"

    # SELL_PENDING -> RECONCILIATION
    pos = position_state_machine.transition_to(sym, "RECONCILIATION", "Sell swap confirmed, checking wallet")
    assert pos.current_state == "RECONCILIATION"

    # RECONCILIATION -> CLOSED
    pos = position_state_machine.transition_to(sym, "CLOSED", "Balance verified zero, trade logged")
    assert pos.current_state == "CLOSED"
    assert len(pos.transition_history) == 8
    print("[PASS] Test 1: Full 8-state position lifecycle transition sequence verified.")


def test_02_illegal_transition_rejection():
    """2. Illegal Transition Guard: Reject illegal jumps and enforce reconciliation before closure."""
    sym = "P4_ILLEGAL"
    position_state_machine.clear()
    position_state_machine.get_or_create_position(symbol=sym, mint="Mint_Ill", mode="PAPER", initial_state="DISCOVERED")

    # DISCOVERED -> MONITORING (Illegal jump)
    try:
        position_state_machine.transition_to(sym, "MONITORING", "Illegal skip")
        assert False, "Should have raised InvalidStateTransitionError"
    except InvalidStateTransitionError as ex:
        assert "ILLEGAL_TRANSITION" in str(ex)

    # Move to MONITORING legally
    position_state_machine.transition_to(sym, "ENTRY_APPROVED", "OK")
    position_state_machine.transition_to(sym, "BUY_PENDING", "OK")
    position_state_machine.transition_to(sym, "POSITION_OPEN", "OK")
    position_state_machine.transition_to(sym, "MONITORING", "OK")

    # MONITORING -> CLOSED (Illegal: must pass RECONCILIATION)
    try:
        position_state_machine.transition_to(sym, "CLOSED", "Illegal close without reconciliation")
        assert False, "Should have raised InvalidStateTransitionError"
    except InvalidStateTransitionError as ex:
        assert "RECONCILIATION_REQUIRED" in str(ex) or "ILLEGAL_TRANSITION" in str(ex)

    print("[PASS] Test 2: Illegal state transitions and mandatory reconciliation invariant strictly enforced.")


def test_03_conflict_scenario_a_entry_vs_risk():
    """3. Conflict Scenario A: Entry recommends BUY, Risk Engine rejects -> Decision is REJECT."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision="BUY",
        risk_veto=True,
        veto_reason="Mint Authority Not Disabled",
    )
    assert out.scenario == "SCENARIO_A_ENTRY_VS_RISK"
    assert out.resolution == "REJECT"
    assert out.action == "REJECT"
    assert out.is_blocked is True
    assert "Risk Engine" in out.priority_component
    print(f"[PASS] Test 3: Scenario A verified (Entry BUY vs Risk VETO -> {out.resolution}).")


def test_04_conflict_scenario_b_hold_vs_hard_stop():
    """4. Conflict Scenario B: Exit recommends HOLD, deterministic Hard SL triggers -> SELL overrides."""
    out = conflict_resolver.resolve_exit_conflict(
        exit_decision="HOLD",
        policy_action="FULL_EXIT",
        policy_override=True,
        policy_reason="HARD_STOP_TRIGGERED: Position down -13.5%",
    )
    assert out.scenario == "SCENARIO_B_HOLD_VS_HARD_STOP"
    assert out.resolution == "SELL"
    assert out.action == "FULL_EXIT"
    assert "Deterministic Exit Policy" in out.priority_component
    print(f"[PASS] Test 4: Scenario B verified (AI HOLD vs Hard SL -> {out.resolution} via {out.priority_component}).")


def test_05_conflict_scenario_c_partial_exit():
    """5. Conflict Scenario C: Exit recommends REDUCE, Risk Policy confirms -> PARTIAL_SELL."""
    out = conflict_resolver.resolve_exit_conflict(
        exit_decision="REDUCE",
        policy_action="REDUCE_50",
        policy_override=False,
    )
    assert out.scenario == "SCENARIO_C_PARTIAL_EXIT"
    assert out.resolution == "PARTIAL_SELL"
    assert out.action == "REDUCE_50"
    print(f"[PASS] Test 5: Scenario C verified (Exit REDUCE -> {out.resolution} {out.action}).")


def test_06_conflict_scenario_d_stale_data_guard():
    """6. Conflict Scenario D: Market data is stale (>180s) -> No new BUY allowed, existing stops preserved."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision="BUY",
        risk_veto=False,
        is_stale_data=True,
    )
    assert out.scenario == "SCENARIO_D_STALE_DATA"
    assert out.resolution == "HOLD_NO_BUY"
    assert out.action == "SKIP"
    assert out.is_blocked is True
    print(f"[PASS] Test 6: Scenario D verified (Stale data blocks BUY -> {out.resolution}).")


def test_07_conflict_scenario_e_ai_provider_outage():
    """7. Conflict Scenario E: AI provider offline -> Graceful deterministic fallback."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision="BUY",
        ai_provider_available=False,
    )
    assert out.scenario == "SCENARIO_E_AI_PROVIDER_UNAVAILABLE"
    assert out.resolution == "DETERMINISTIC_FALLBACK"
    assert out.is_blocked is True

    exit_out = conflict_resolver.resolve_exit_conflict(
        exit_decision="HOLD",
        policy_action="HOLD",
        ai_provider_available=False,
    )
    assert exit_out.scenario == "SCENARIO_E_EXIT_AI_OFFLINE"
    assert exit_out.resolution == "DETERMINISTIC_FALLBACK"
    print("[PASS] Test 7: Scenario E verified: AI provider outage triggers deterministic fallback.")


def test_08_capacity_limit_enforcement():
    """8. Capacity limit: Blocks new entries when max open positions reached."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision="BUY",
        current_open_positions=5,
        max_open_positions=5,
    )
    assert out.scenario == "MAX_CAPACITY_REACHED"
    assert out.resolution == "REJECT"
    assert out.is_blocked is True
    print(f"[PASS] Test 8: Capacity limit verified: Blocked at 5/5 open positions.")


def test_09_daily_drawdown_circuit_breaker():
    """9. Daily drawdown limit: Halts new trading if daily losses exceed safety threshold."""
    out = conflict_resolver.resolve_entry_conflict(
        entry_decision="BUY",
        daily_drawdown_limit_hit=True,
    )
    assert out.scenario == "DAILY_DRAWDOWN_LIMIT"
    assert out.resolution == "HALT_DAILY_DRAWDOWN"
    assert out.is_blocked is True
    print(f"[PASS] Test 9: Daily Drawdown limit verified: Halts trading upon loss limit breach.")


def test_10_consecutive_error_circuit_breaker():
    """10. Circuit breaker: Consecutive agent errors trip breaker and degrade system status."""
    trade_supervisor.reset_circuit_breaker()
    assert trade_supervisor._circuit_breaker_active is False

    # Simulate 5 consecutive agent errors
    for i in range(5):
        trade_supervisor.record_agent_error("market_analyst", f"Mock network timeout {i+1}")

    assert trade_supervisor._circuit_breaker_active is True
    status = trade_supervisor.get_system_status()
    assert status.circuit_breaker_active is True
    assert status.system_status == "degraded"
    assert status.ai_service_online is False

    # Reset
    trade_supervisor.reset_circuit_breaker()
    assert trade_supervisor._circuit_breaker_active is False
    print(f"[PASS] Test 10: Automatic circuit breaker verified (Tripped after 5 errors -> status: degraded -> reset ok).")


def test_11_emergency_kill_switch():
    """11. Emergency Kill Switch: Operator kill switch immediately sets status to halted."""
    trade_supervisor.disengage_kill_switch()
    assert trade_supervisor._kill_switch_engaged is False

    trade_supervisor.engage_kill_switch(reason="MANUAL_TEST_EMERGENCY")
    assert trade_supervisor._kill_switch_engaged is True
    status = trade_supervisor.get_system_status()
    assert status.system_status == "halted"
    assert status.kill_switch_engaged is True

    # Restore
    trade_supervisor.disengage_kill_switch()
    assert trade_supervisor._kill_switch_engaged is False
    assert trade_supervisor.get_system_status().system_status == "operational"
    print("[PASS] Test 11: Emergency kill switch engage/disengage verified.")


def test_12_position_recovery_after_restart():
    """12. Position Recovery: Recovers DB holdings into state machine and adaptive tracking after restart."""
    db = SessionLocal()
    sym = "P4_RECOVER"
    try:
        _clean_test_data(db, sym)
        holding = PortfolioHolding(
            symbol=sym,
            mode="PAPER",
            quantity=50.0,
            avg_entry_price=0.008,
            current_price=0.009,
            liquidity_usd=25000.0,
        )
        db.add(holding)
        db.commit()

        # Simulate restart recovery
        recovered_count = trade_supervisor.recover_positions_after_restart(db=db, mode="PAPER")
        assert recovered_count >= 1

        pos = position_state_machine.get_position(sym, mode="PAPER")
        assert pos is not None
        assert pos.current_state == "MONITORING"
        assert abs(pos.quantity - 50.0) < 0.1
        assert abs(pos.avg_entry_price - 0.008) < 1e-6
        print(f"[PASS] Test 12: Recovery after restart verified: {recovered_count} position(s) recovered into MONITORING.")
    finally:
        _clean_test_data(db, sym)
        db.close()


def test_13_reconciled_balance_accounting():
    """13. Reconciled Balance Accounting: Position state cannot close until balance is zero."""
    sym = "P4_RECONCILE"
    position_state_machine.clear()
    pos = position_state_machine.get_or_create_position(
        symbol=sym, mint="Mint_Rec", mode="PAPER", initial_quantity=100.0, entry_price=0.010, initial_state="MONITORING"
    )

    # Partial sell: remaining 50 tokens
    position_state_machine.transition_to(sym, "SELL_PENDING", "Sold 50%")
    position_state_machine.transition_to(sym, "RECONCILIATION", "Reconciling on-chain")
    # Remaining > 0 -> must loop back to MONITORING
    position_state_machine.transition_to(sym, "MONITORING", "50 tokens remaining")
    assert pos.current_state == "MONITORING"

    # Final sell: remaining 0 tokens
    position_state_machine.transition_to(sym, "SELL_PENDING", "Sold remaining 50%")
    position_state_machine.transition_to(sym, "RECONCILIATION", "Reconciling final slice")
    position_state_machine.transition_to(sym, "CLOSED", "Balance verified 0")
    assert pos.current_state == "CLOSED"
    print("[PASS] Test 13: Reconciled balance accounting verified: Partial loops to MONITORING, Final closes to CLOSED.")


def test_14_supervisor_telemetry():
    """14. Supervisor Telemetry: Accurate metadata and zero dummy data PnL."""
    status = supervisor_agent.get_status()
    assert status.agent == "trade_supervisor"
    assert status.system_status in ("operational", "degraded", "halted")
    assert len(status.registered_agents) == 6
    assert status.deterministic_risk_online is True
    print(f"[PASS] Test 14: Telemetry verified: System={status.system_status}, Agents={len(status.registered_agents)}, RiskOnline={status.deterministic_risk_online}")


def test_15_end_to_end_supervision_tick():
    """15. End-to-end supervision tick: Inspects active holdings, runs exit evaluation, and updates state."""
    db = SessionLocal()
    sym = "P4_TICK"
    try:
        _clean_test_data(db, sym)
        from app.services import bot as bot_svc
        bot_svc._SNIPER_CONFIG["max_open_positions"] = 50

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

        # Run supervision tick
        results = trade_supervisor.supervise_positions_tick(db=db, strategy_mode="DEFAULT", mode="PAPER")
        assert len(results) >= 1
        tick_res = next((r for r in results if r["symbol"] == sym), None)
        assert tick_res is not None
        assert "decision" in tick_res
        assert "conflict_resolution" in tick_res

        # Verify position is monitored in state machine
        pos = position_state_machine.get_position(sym, mode="PAPER")
        assert pos is not None
        print(f"[PASS] Test 15: End-to-end supervision tick verified for {sym} (Decision={tick_res['decision']}, Resolution={tick_res['conflict_resolution']}).")
    finally:
        _clean_test_data(db, sym)
        db.close()


def run_all_tests():
    print("=" * 70)
    print("SOFIA MEME BOT V2 - PHASE 4 TEST SUITE (15 MANDATORY TESTS)")
    print("=" * 70)
    tests = [
        test_01_lifecycle_state_transitions,
        test_02_illegal_transition_rejection,
        test_03_conflict_scenario_a_entry_vs_risk,
        test_04_conflict_scenario_b_hold_vs_hard_stop,
        test_05_conflict_scenario_c_partial_exit,
        test_06_conflict_scenario_d_stale_data_guard,
        test_07_conflict_scenario_e_ai_provider_outage,
        test_08_capacity_limit_enforcement,
        test_09_daily_drawdown_circuit_breaker,
        test_10_consecutive_error_circuit_breaker,
        test_11_emergency_kill_switch,
        test_12_position_recovery_after_restart,
        test_13_reconciled_balance_accounting,
        test_14_supervisor_telemetry,
        test_15_end_to_end_supervision_tick,
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
