"""
Phase 7: Controlled LIVE Deployment & Pre-Flight Security Test Suite.
Verifies:
1. Default SAFE/LOCKED state for live execution.
2. Cryptographic authorization unlock and immediate revocation.
3. Pre-flight gas reserve invariant (0.05 SOL) and allocation ceiling.
4. Supervisor kill-switch and emergency circuit breaker blocking.
5. Trade Quality Gate hard veto preventing unauthorized on-chain transactions.
6. FastAPI REST endpoints for live status, pre-flight audit, authorize, and revoke.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base
from app.v2.services.live_executor import V2LiveExecutor
from app.v2.core.supervisor import AutonomousTradeSupervisor
from app.v2.core.quality_gate import QualityGateResult
from app.v2.ai.schemas import EntryDecisionOutput, EntryZone


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


@pytest.fixture(autouse=True)
def reset_live_state():
    """Ensure clean authorization state before and after each test."""
    V2LiveExecutor._live_authorized = False
    V2LiveExecutor._authorization_timestamp = None
    V2LiveExecutor._authorized_by = None
    yield
    V2LiveExecutor._live_authorized = False


def test_01_live_authorization_lock_by_default(test_db):
    """
    Test 1: Verifies that Phase 7 LIVE trading is strictly locked by default
    and any live execution attempt raises PermissionError.
    """
    assert V2LiveExecutor.is_authorized() is False

    mock_decision = EntryDecisionOutput(
        agent="entry_intelligence",
        mint="Mint1111111111111111111111111111111111111111",
        symbol="TEST",
        decision="BUY",
        score=85.0,
        confidence="high",
        entry_zone=EntryZone(min=0.04, max=0.05),
        invalidation=0.035,
        expected_rr_ratio=3.0,
        data_timestamp=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_gate = QualityGateResult(
        passed=True,
        verdict="APPROVED",
        rejection_reasons=[],
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )

    with pytest.raises(PermissionError) as exc_info:
        V2LiveExecutor.execute_live_entry(
            db=test_db,
            entry_decision=mock_decision,
            quality_gate_result=mock_gate,
            allocation_sol=0.02,
        )
    assert "NOT authorized" in str(exc_info.value)


def test_02_authorization_unlock_and_revocation():
    """
    Test 2: Verifies authorization unlock with valid confirmation code and immediate revocation.
    """
    # Invalid code fails
    with pytest.raises(ValueError) as exc:
        V2LiveExecutor.authorize_live_deployment(confirmation_code="WRONG_CODE")
    assert "Invalid confirmation code" in str(exc.value)
    assert V2LiveExecutor.is_authorized() is False

    # Valid code succeeds
    res = V2LiveExecutor.authorize_live_deployment(
        authority="DSLN Capital CEO",
        confirmation_code="DSLN-LIVE-AUTHORIZATION-CONFIRMED",
    )
    assert res["status"] == "AUTHORIZED"
    assert res["authorized_by"] == "DSLN Capital CEO"
    assert V2LiveExecutor.is_authorized() is True

    # Revocation immediately locks the engine
    rev = V2LiveExecutor.revoke_live_deployment(reason="TEST_REVOCATION")
    assert rev["status"] == "REVOKED"
    assert V2LiveExecutor.is_authorized() is False


def test_03_preflight_checks_and_gas_reserve_invariant():
    """
    Test 3: Verifies pre-flight gas reserve checks (0.05 SOL minimum) and allocation caps.
    """
    # Mock wallet with 0.08 SOL balance
    with patch("app.services.solana_trader.get_trading_keypair") as mock_kp, \
         patch("app.services.solana_trader.get_sol_balance", return_value=0.08):
        mock_kp.return_value.pubkey.return_value = "MockSolanaWalletPublicKey111111111111111111"

        # Check when not authorized
        res_unauth = V2LiveExecutor.run_preflight_checks(requested_sol=0.02)
        assert res_unauth["ready"] is False
        assert any("NOT_AUTHORIZED" in r for r in res_unauth["rejection_reasons"])
        assert res_unauth["reserved_gas_sol"] == 0.05
        assert res_unauth["available_trading_sol"] == 0.03  # 0.08 - 0.05

        # Authorize and test valid allocation
        V2LiveExecutor.authorize_live_deployment(confirmation_code="DSLN-LIVE-AUTHORIZATION-CONFIRMED")
        res_auth = V2LiveExecutor.run_preflight_checks(requested_sol=0.02)
        assert res_auth["ready"] is True
        assert len(res_auth["rejection_reasons"]) == 0

        # Allocation exceeding available trading capital
        res_excess = V2LiveExecutor.run_preflight_checks(requested_sol=0.04)
        assert res_excess["ready"] is False
        assert any("INSUFFICIENT_TRADING_CAPITAL" in r for r in res_excess["rejection_reasons"])

        # Allocation exceeding hard ceiling (0.05 SOL)
        res_ceiling = V2LiveExecutor.run_preflight_checks(requested_sol=0.06)
        assert res_ceiling["ready"] is False
        assert any("ALLOCATION_EXCEEDS_CEILING" in r for r in res_ceiling["rejection_reasons"])


def test_04_supervisor_kill_switch_blocking(test_db):
    """
    Test 4: Verifies that supervisor kill switch prevents live execution even if authorized.
    """
    V2LiveExecutor.authorize_live_deployment(confirmation_code="DSLN-LIVE-AUTHORIZATION-CONFIRMED")

    supervisor = AutonomousTradeSupervisor()
    supervisor.engage_kill_switch(reason="EMERGENCY_AUDIT_HALT")

    mock_decision = EntryDecisionOutput(
        agent="entry_intelligence",
        mint="Mint1111111111111111111111111111111111111111",
        symbol="TEST",
        decision="BUY",
        score=85.0,
        confidence="high",
        entry_zone=EntryZone(min=0.04, max=0.05),
        invalidation=0.035,
        expected_rr_ratio=3.0,
        data_timestamp=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_gate = QualityGateResult(
        passed=True,
        verdict="APPROVED",
        rejection_reasons=[],
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )

    with pytest.raises(RuntimeError) as exc_info:
        V2LiveExecutor.execute_live_entry(
            db=test_db,
            entry_decision=mock_decision,
            quality_gate_result=mock_gate,
            allocation_sol=0.02,
            supervisor=supervisor,
        )
    assert "Kill Switch" in str(exc_info.value)


def test_05_trade_quality_gate_hard_veto_on_live(test_db):
    """
    Test 5: Verifies that Quality Gate rejection prevents live execution without touching blockchain.
    """
    V2LiveExecutor.authorize_live_deployment(confirmation_code="DSLN-LIVE-AUTHORIZATION-CONFIRMED")

    mock_decision = EntryDecisionOutput(
        agent="entry_intelligence",
        mint="Mint1111111111111111111111111111111111111111",
        symbol="TEST",
        decision="SKIP",
        score=62.0,
        confidence="low",
        entry_zone=EntryZone(min=0.04, max=0.05),
        invalidation=0.035,
        expected_rr_ratio=1.0,
        data_timestamp=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_gate = QualityGateResult(
        passed=False,
        verdict="REJECT_RISK_VETO",
        rejection_reasons=["High dev holding (18% > 10%)"],
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )

    with pytest.raises(ValueError) as exc:
        V2LiveExecutor.execute_live_entry(
            db=test_db,
            entry_decision=mock_decision,
            quality_gate_result=mock_gate,
            allocation_sol=0.02,
        )
    assert "Quality Gate rejected" in str(exc.value)


def test_06_fastapi_endpoints():
    """
    Test 6: Tests FastAPI REST endpoints for live status, preflight, authorize, and revoke.
    """
    client = TestClient(app)

    # 1. Status endpoint
    res_status = client.get("/api/v2/supervisor/live/status")
    assert res_status.status_code == 200
    d_status = res_status.json()
    assert d_status["phase"] == "PHASE_7_CONTROLLED_LIVE"
    assert d_status["min_sol_reserve"] == 0.05
    assert d_status["max_canary_allocation_sol"] == 0.05
    assert d_status["is_authorized"] is False

    # 2. Preflight endpoint
    res_pre = client.get("/api/v2/supervisor/live/preflight?requested_sol=0.02")
    assert res_pre.status_code == 200
    d_pre = res_pre.json()
    assert "ready" in d_pre
    assert d_pre["reserved_gas_sol"] == 0.05

    # 3. Authorize endpoint
    res_auth = client.post(
        "/api/v2/supervisor/live/authorize",
        json={"authority": "DSLN Capital CEO", "confirmation_code": "DSLN-LIVE-AUTHORIZATION-CONFIRMED"}
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "AUTHORIZED"

    # Status reflects authorization
    res_status2 = client.get("/api/v2/supervisor/live/status")
    assert res_status2.json()["is_authorized"] is True

    # 4. Revoke endpoint
    res_rev = client.post(
        "/api/v2/supervisor/live/revoke",
        json={"reason": "ROUTINE_SECURITY_LOCK"}
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "REVOKED"

    # Status reflects locked
    res_status3 = client.get("/api/v2/supervisor/live/status")
    assert res_status3.json()["is_authorized"] is False
