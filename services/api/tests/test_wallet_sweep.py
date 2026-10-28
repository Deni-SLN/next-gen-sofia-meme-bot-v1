"""Profit sweep & wallet withdrawal tests (PRD §18.F).

The contract under test: money can never leave a wallet without an explicit,
audited, allowlisted, idempotent and fail-closed path. PAPER never signs.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.errors import ConflictError, ForbiddenError, ValidationError
from app.models.trading import AccountingEvent, BotRun, Position
from app.models.wallet import (
    ProfitSweepEvent,
    WalletAccount,
    WalletBalanceSnapshot,
    WalletTransfer,
    WithdrawalIntent,
)
from app.services import wallet_service as ws

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = ws.USDC_MAINNET_MINT
SOL_DEC = 9

# USD -> lamports uses /100 because 1 SOL is priced against 100 USD in the
# conservative reserve mapping (wallet_service.compute_dynamic_reserve).
def usd_to_atomic(usd: float, decimals: int = SOL_DEC) -> int:
    return int(round(usd * (10**decimals) / 100.0))


# ----------------------------- Fixtures -----------------------------


@pytest.fixture()
def wallets(db):
    """MAIN is registered first so it becomes the allowlisted treasury."""
    main = ws.register_wallet(db, "MAIN", "MainTreasuryAddress1111111111111", "op")
    bot = ws.register_wallet(db, "BOT", "BotWalletAddress22222222222222222", "op")
    return {"main": main, "bot": bot}


@pytest.fixture()
def funded(wallets, db):
    """A fresh SOL snapshot with plenty of headroom."""
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    return wallets


def _closed_position(db, realized_pnl: float, status: str = "CLOSED"):
    run = db.query(BotRun).first()
    if run is None:
        run = BotRun(mode="PAPER", status="RUNNING")
        db.add(run)
        db.flush()
    from app.models.market import Token

    token = db.query(Token).first()
    if token is None:
        token = Token(chain="solana", mint_address=SOL_MINT, symbol="T")
        db.add(token)
        db.flush()
    pos = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=SOL_MINT,
        quantity=0.0,
        average_entry_price=0.0,
        status=status,
        realized_pnl=realized_pnl,
    )
    db.add(pos)
    db.commit()
    return pos


def _mk_open(db, notional_usd: float) -> Position:
    run = db.query(BotRun).first()
    if run is None:
        run = BotRun(mode="PAPER", status="RUNNING")
        db.add(run)
        db.flush()
    from app.models.market import Token

    token = db.query(Token).first()
    if token is None:
        token = Token(chain="solana", mint_address=SOL_MINT, symbol="T")
        db.add(token)
        db.flush()
    # quantity 1 at entry price == notional, so exposure == notional
    pos = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=SOL_MINT,
        quantity=1.0,
        average_entry_price=notional_usd,
        status="OPEN",
        realized_pnl=0.0,
    )
    db.add(pos)
    db.commit()
    return pos


def _pending_intent(db, source_id, dest_id, amount_atomic, state="VALIDATING", key=None):
    import uuid

    intent = WithdrawalIntent(
        idempotency_key=key or f"pending-{uuid.uuid4().hex[:12]}",
        trigger_type="MANUAL",
        source_wallet_id=source_id,
        destination_wallet_id=dest_id,
        destination_address_snapshot="MainTreasuryAddress1111111111111",
        asset="SOL",
        mint_address=SOL_MINT,
        amount_atomic=amount_atomic,
        estimated_fee_atomic=5_000,
        reserve_snapshot={},
        policy_version=1,
        state=state,
    )
    db.add(intent)
    db.commit()
    return intent


def _intent(db, wallets, amount_atomic=1_000_000, key="k1", gate=True):
    if gate:
        ws.set_wallet_enabled(db, True, "op")
    return ws.create_withdrawal_intent(
        db, "op", wallets["bot"].id, "SOL", amount_atomic, key
    )


# ----------------------------- Gates -----------------------------


def test_wallet_gate_defaults_off(db):
    assert ws.is_wallet_enabled(db) is False


def test_sweep_gate_defaults_off(db):
    assert ws.is_sweep_enabled(db) is False


def test_wallet_gate_toggles(db):
    ws.set_wallet_enabled(db, True, "op")
    assert ws.is_wallet_enabled(db) is True
    ws.set_wallet_enabled(db, False, "op")
    assert ws.is_wallet_enabled(db) is False


# ----------------------------- State machine -----------------------------


def test_state_machine_allows_every_legal_transition(funded, db, wallets):
    legal = {
        "DRAFT": ["VALIDATING", "CANCELLED"],
        "VALIDATING": ["AWAITING_CONFIRMATION", "READY_TO_SIGN", "REJECTED"],
        "AWAITING_CONFIRMATION": ["READY_TO_SIGN", "CANCELLED", "REJECTED"],
        "READY_TO_SIGN": ["SIGNING", "CANCELLED", "REJECTED"],
        "SIGNING": ["SUBMITTED", "FAILED"],
        "SUBMITTED": ["CONFIRMING", "FAILED"],
        "CONFIRMING": ["CONFIRMED", "FAILED", "RECONCILIATION_REQUIRED"],
        "RECONCILIATION_REQUIRED": ["CONFIRMED", "FAILED"],
    }
    for frm, targets in legal.items():
        for to in targets:
            intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, frm)
            ws.set_wallet_enabled(db, True, "op")
            ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
            out = ws.transition_intent(db, intent.id, "op", to)
            assert out["state"] == to, f"{frm} -> {to} must be allowed"


def test_illegal_transition_is_rejected(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "DRAFT")
    with pytest.raises(ValidationError):
        ws.transition_intent(db, intent.id, "op", "SUBMITTED")


def test_terminal_state_is_immutable(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMED")
    with pytest.raises(ConflictError):
        ws.transition_intent(db, intent.id, "op", "SIGNING")


def test_unknown_intent_is_not_found(db):
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        ws.transition_intent(db, "does-not-exist", "op", "VALIDATING")


# ----------------------------- Reconciliation -----------------------------


def test_reconciliation_required_reaches_final_state(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "RECONCILIATION_REQUIRED")
    out = ws.reconcile_intent(db, intent.id, "op", "CONFIRMED", signature="sig-abc")
    assert out["state"] == "CONFIRMED"


def test_reconciliation_failure_path(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMING")
    out = ws.reconcile_intent(db, intent.id, "op", "FAILED")
    assert out["state"] == "FAILED"


def test_confirmed_requires_signature(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMING")
    with pytest.raises(ValidationError):
        ws.reconcile_intent(db, intent.id, "op", "CONFIRMED")


def test_reconcile_rejects_unknown_outcome(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMING")
    with pytest.raises(ValidationError):
        ws.reconcile_intent(db, intent.id, "op", "MAYBE")


def test_same_signature_cannot_attach_to_two_intents(funded, db, wallets):
    a = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMING")
    b = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 2_000, "CONFIRMING")
    ws.reconcile_intent(db, a.id, "op", "CONFIRMED", signature="dup-sig")
    with pytest.raises(ConflictError):
        ws.reconcile_intent(db, b.id, "op", "CONFIRMED", signature="dup-sig")


def test_reconcile_refuses_terminal_intent(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CANCELLED")
    with pytest.raises(ValidationError):
        ws.reconcile_intent(db, intent.id, "op", "CONFIRMED", signature="s")


def test_one_transfer_row_per_intent(funded, db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "CONFIRMING")
    ws.reconcile_intent(db, intent.id, "op", "CONFIRMED", signature="s1")
    assert db.query(WalletTransfer).filter_by(withdrawal_intent_id=intent.id).count() == 1
    # A confirmed intent is terminal: re-reconciling is refused rather than
    # silently appending a second transfer row.
    with pytest.raises(ValidationError):
        ws.reconcile_intent(db, intent.id, "op", "CONFIRMED", signature="s1")
    assert db.query(WalletTransfer).filter_by(withdrawal_intent_id=intent.id).count() == 1


# ----------------------------- Idempotency -----------------------------


def test_same_key_same_payload_deduplicates(funded, db, wallets):
    first = _intent(db, wallets, 1_000_000, key="same-key")
    second = _intent(db, wallets, 1_000_000, key="same-key")
    assert first["deduplicated"] is False
    assert second["deduplicated"] is True
    assert first["intent"]["id"] == second["intent"]["id"]


def test_same_key_different_payload_conflicts(funded, db, wallets):
    _intent(db, wallets, 1_000_000, key="conflict-key")
    with pytest.raises(ConflictError) as exc:
        _intent(db, wallets, 2_000_000, key="conflict-key")
    assert exc.value.details.get("code") == "IDEMPOTENCY_CONFLICT"


def test_payload_hash_is_stable():
    a = ws._payload_hash({"x": 1, "y": 2})
    b = ws._payload_hash({"y": 2, "x": 1})
    assert a == b


def test_idempotency_key_is_required(funded, db, wallets):
    with pytest.raises(ValidationError):
        ws.create_withdrawal_intent(db, "op", wallets["bot"].id, "SOL", 1_000, "")


def test_amount_must_be_positive(funded, db, wallets):
    with pytest.raises(ValidationError):
        ws.create_withdrawal_intent(db, "op", wallets["bot"].id, "SOL", 0, "k-zero")


def test_unknown_trigger_type_rejected(funded, db, wallets):
    with pytest.raises(ValidationError):
        ws.create_withdrawal_intent(
            db, "op", wallets["bot"].id, "SOL", 1_000, "k", trigger_type="SNEAKY"
        )


# ----------------------------- Reserve -----------------------------


def test_reserve_includes_buffer_and_pending(funded, db, wallets):
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 700_000_000, "VALIDATING")
    r = ws.compute_dynamic_reserve(db, wallets["bot"].id, "SOL")
    assert r.pending_outflows_atomic == 700_000_000 + 5_000
    assert r.operational_buffer_atomic == 5_000
    assert r.total_atomic == r.pending_outflows_atomic + r.operational_buffer_atomic


def test_reserve_counts_open_position_exposure(db, wallets):
    _mk_open(db, 100.0)  # exposure 100 USD
    r = ws.compute_dynamic_reserve(db, wallets["bot"].id, "SOL")
    assert r.open_position_exposure_atomic > 0


def test_terminal_intents_do_not_count_as_pending(funded, db, wallets):
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 700_000_000, "REJECTED")
    r = ws.compute_dynamic_reserve(db, wallets["bot"].id, "SOL")
    assert r.pending_outflows_atomic == 0


# ----------------------------- Sweep math -----------------------------


def test_sweep_without_profit_is_zero(funded, db, wallets):
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.sweepable_atomic == 0


def test_sweep_is_capped_at_fifty_percent(funded, db, wallets):
    _closed_position(db, realized_pnl=100.0)
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.eligible_realized_atomic == usd_to_atomic(100.0)
    assert ev.sweepable_atomic == ev.eligible_realized_atomic // 2


def test_sweep_ignores_unrealized_profit(db, wallets):
    _closed_position(db, realized_pnl=0.0, status="OPEN")
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.eligible_realized_atomic == 0
    assert ev.sweepable_atomic == 0


def test_stale_balance_snapshot_fails_closed(db, wallets):
    ws.record_balance_snapshot(
        db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT,
        observed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.sweepable_atomic == 0
    assert any("stale" in r for r in ev.reasons)


def test_pending_outflow_is_not_double_counted(db, wallets):
    """Regression: reserve.total already contains pending, so subtracting it
    again would zero out a sweep that is actually affordable."""
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 2_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)  # eligible -> 1e9, 50% -> 5e8
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_800_000_000, "VALIDATING")

    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    reserve_total = ev.reserve_atomic  # exposure 0 + pending 1.800005e9 + buffer 5000
    expected = max(0, ev.available_atomic - reserve_total - ev.fee_atomic)
    assert expected > 0, "fixture must leave affordable headroom"
    assert ev.sweepable_atomic == min(ev.eligible_realized_atomic // 2, expected)


def test_already_swept_profit_is_not_swept_twice(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    full = usd_to_atomic(100.0)
    db.add(
        ProfitSweepEvent(
            close_event_id="c1",
            asset="SOL",
            realized_profit_atomic=full,
            sweep_percent=50,
            sweep_amount_atomic=full,
            policy_version=1,
            status="INTENT_CREATED",
        )
    )
    db.commit()
    assert ws.eligible_realized_profit_atomic(db, "SOL") == 0


def test_realized_loss_produces_no_sweep(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=-50.0)
    assert ws.eligible_realized_profit_atomic(db, "SOL") == 0


def test_ledger_realized_pnl_counts(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    db.add(AccountingEvent(mode="PAPER", event_type="REALIZED_PNL", amount=10.0))
    db.commit()
    assert ws.eligible_realized_profit_atomic(db, "SOL") == usd_to_atomic(10.0)


def test_usdc_profit_uses_one_to_one_usd_conversion(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "USDC", 500_000_000, USDC_MINT)
    _closed_position(db, realized_pnl=100.0)
    # 100 USD = 100_000_000 micro-USDC (6 decimals), 50% sweepable = 50_000_000
    assert ws.eligible_realized_profit_atomic(db, "USDC") == 100_000_000
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "USDC")
    assert ev.sweepable_atomic == 50_000_000


def test_get_bot_wallet_returns_the_active_bot(db, wallets):
    assert ws.get_bot_wallet(db).id == wallets["bot"].id
    assert ws.get_bot_wallet(db).wallet_role == "BOT"
    wallets["bot"].status = "PAUSED"
    db.commit()
    assert ws.get_bot_wallet(db) is None, "a non-ACTIVE bot wallet is not a sweep source"


def test_get_main_wallet_is_deterministic(db, wallets):
    assert ws.get_main_wallet(db).id == wallets["main"].id
    assert ws.get_main_wallet(db).is_allowlisted == 1


# ----------------------------- Policy inheritance -----------------------------


def test_set_policy_inherits_fields_it_does_not_change(db, wallets):
    """A partial update must not silently reset the other policy fields."""
    ws.set_policy(db, "op", {"sweep_percent": 25, "min_sweep_atomic": 0})
    ws.set_policy(db, "op", {"cooldown_seconds": 60})
    p = ws.get_policy(db)
    assert p.sweep_percent == 25, "unchanged field was reset by the second update"
    assert p.cooldown_seconds == 60
    assert p.version == 3, "each update is a new immutable version"
    assert list(p.allowed_assets) == list(ws.ALLOWED_ASSETS)


def test_set_policy_audit_lists_only_the_changed_fields(db, wallets):
    ws.set_policy(db, "op", {"sweep_percent": 30})
    from app.models.ops import AuditLog

    row = db.query(AuditLog).filter(AuditLog.action == "update_wallet_policy").order_by(
        AuditLog.created_at.desc()
    ).first()
    assert row is not None
    assert row.metadata_json["changed"] == ["sweep_percent"]
    assert row.metadata_json["version"] == 2


# ----------------------------- Sweep percent -----------------------------


def test_sweep_uses_the_policy_percent_not_a_hardcoded_half(db, wallets):
    """Regression: evaluate_sweep used 0.5 regardless of policy.sweep_percent."""
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_policy(db, "op", {"sweep_percent": 25, "min_sweep_atomic": 0})
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.eligible_realized_atomic == usd_to_atomic(100.0)
    assert ev.sweepable_atomic == ev.eligible_realized_atomic * 25 // 100


def test_zero_sweep_percent_sweeps_nothing(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_policy(db, "op", {"sweep_percent": 0, "min_sweep_atomic": 0})
    ev = ws.evaluate_sweep(db, wallets["bot"].id, "SOL")
    assert ev.sweepable_atomic == 0


# ----------------------------- Missing snapshot fails closed -----------------------------


def test_creating_an_intent_without_a_balance_snapshot_fails_closed(db, wallets):
    """A None snapshot must be a ValidationError, not an AttributeError 500."""
    with pytest.raises(ValidationError) as exc:
        ws.create_withdrawal_intent(db, "op", wallets["bot"].id, "SOL", 1_000_000, "no-snap-key")
    assert "snapshot" in str(exc.value).lower()
    assert db.query(WithdrawalIntent).count() == 0


# ----------------------------- Auto sweep -----------------------------


def test_auto_sweep_skipped_when_gate_off(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    out = ws.evaluate_and_record_sweep(db, "op", "close-1", wallets["bot"].id, "SOL")
    assert out["status"] == "SKIPPED"
    assert out["sweepable_atomic"] == 0


def test_auto_sweep_creates_intent_when_enabled(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_sweep_enabled(db, True, "op")
    ws.set_wallet_enabled(db, True, "op")
    out = ws.evaluate_and_record_sweep(db, "op", "close-2", wallets["bot"].id, "SOL")
    assert out["status"] == "INTENT_CREATED"
    assert out["sweepable_atomic"] > 0


def test_auto_sweep_records_event_once_per_close(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_sweep_enabled(db, True, "op")
    ws.set_wallet_enabled(db, True, "op")
    a = ws.evaluate_and_record_sweep(db, "op", "close-3", wallets["bot"].id, "SOL")
    b = ws.evaluate_and_record_sweep(db, "op", "close-3", wallets["bot"].id, "SOL")
    assert b["deduplicated"] is True
    assert db.query(ProfitSweepEvent).filter_by(close_event_id="close-3").count() == 1
    assert a["event_id"] == b["event_id"]


def test_sweep_failure_does_not_break_engine(db, wallets):
    """A sweep that cannot proceed must record SKIPPED, not raise."""
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_sweep_enabled(db, True, "op")
    out = ws.evaluate_and_record_sweep(db, "op", "close-4", wallets["bot"].id, "SOL")
    assert out["status"] in ("SKIPPED", "INTENT_CREATED")


# ----------------------------- Transfer validation -----------------------------


def test_validate_transfer_reports_full_confirmation_view(funded, db, wallets):
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000)
    for key in (
        "source_address", "destination_address", "asset", "amount_atomic",
        "amount_ui", "estimated_fee_atomic", "reserve_atomic", "balance_after_atomic",
        "policy_version", "checks",
    ):
        assert key in rep
    assert rep["source_address"] == "BotWalletAddress22222222222222222"
    assert rep["destination_address"] == "MainTreasuryAddress1111111111111"


def test_validate_transfer_never_creates_an_intent(funded, db, wallets):
    ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000)
    assert db.query(WithdrawalIntent).count() == 0


def test_validate_transfer_fails_on_stale_balance(db, wallets):
    ws.record_balance_snapshot(
        db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT,
        observed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000)
    assert rep["valid"] is False
    assert "balance_snapshot_fresh" in rep["failed_checks"]


def test_only_sol_and_usdc_allowed(funded, db, wallets):
    rep = ws.validate_transfer(db, wallets["bot"].id, "WBTC", 1_000_000)
    assert rep["valid"] is False
    assert "asset_allowed" in rep["failed_checks"]


def test_dust_amount_rejected(funded, db, wallets):
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 100)
    assert rep["valid"] is False
    assert "not_dust" in rep["failed_checks"]


def test_non_main_destination_rejected(funded, db, wallets):
    other = ws.register_wallet(db, "MAIN", "SecondTreasury3333333333333333333", "op", allowlisted=0)
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000, destination_wallet_id=other.id)
    assert rep["valid"] is False
    assert "destination_allowlisted" in rep["failed_checks"]


def test_source_cannot_be_destination(funded, db, wallets):
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000, destination_wallet_id=wallets["bot"].id)
    assert rep["valid"] is False


def test_usdc_transfer_requires_sol_fee_balance(db, wallets):
    ws.record_balance_snapshot(db, wallets["bot"].id, "USDC", 5_000_000, USDC_MINT)
    rep = ws.validate_transfer(db, wallets["bot"].id, "USDC", 1_000_000)
    assert rep["valid"] is False
    assert "sol_fee_reserve_available" in rep["failed_checks"]


def test_per_transfer_cap_enforced(db, wallets):
    ws.set_policy(db, "op", {"per_transfer_cap_atomic": 2_000_000, "min_sweep_atomic": 0})
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 5_000_000)
    assert rep["valid"] is False
    assert "within_per_transfer_cap" in rep["failed_checks"]


def test_daily_cap_enforced(db, wallets):
    ws.set_policy(db, "op", {"daily_cap_atomic": 3_000_000, "min_sweep_atomic": 0})
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 2_500_000, "VALIDATING")
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000)
    assert rep["valid"] is False
    assert "within_daily_cap" in rep["failed_checks"]


def test_cooldown_blocks_second_intent(db, wallets):
    ws.set_policy(db, "op", {"cooldown_seconds": 3600, "min_sweep_atomic": 0})
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000_000, "VALIDATING")
    rep = ws.validate_transfer(db, wallets["bot"].id, "SOL", 1_000_000)
    assert rep["valid"] is False
    assert "cooldown_elapsed" in rep["failed_checks"]


# ----------------------------- Feature gate -----------------------------


def test_signing_states_blocked_when_wallet_gate_off(funded, db, wallets):
    for state, target in (
        ("VALIDATING", "READY_TO_SIGN"),
        ("READY_TO_SIGN", "SIGNING"),
        ("SIGNING", "SUBMITTED"),
    ):
        intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, state)
        with pytest.raises(ForbiddenError):
            ws.transition_intent(db, intent.id, "op", target)


def test_stale_balance_at_signing_gate_rejects_intent(db, wallets):
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000_000, "VALIDATING")
    ws.set_wallet_enabled(db, True, "op")
    with pytest.raises(ValidationError):
        ws.transition_intent(db, intent.id, "op", "READY_TO_SIGN")
    db.refresh(intent)
    assert intent.state == "REJECTED"


def test_paper_mode_never_signs(funded, db, wallets):
    """No PAPER transfer may ever carry a signature."""
    ws.set_wallet_enabled(db, True, "op")
    intent = _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000, "READY_TO_SIGN")
    ws.transition_intent(db, intent.id, "op", "SIGNING")
    assert db.query(WalletTransfer).count() == 0


# ----------------------------- Secrets -----------------------------


def test_no_private_key_material_is_persisted(funded, db, wallets):
    ws.set_policy(db, "op", {"min_sweep_atomic": 0})
    _pending_intent(db, wallets["bot"].id, wallets["main"].id, 1_000_000, "VALIDATING")
    banned = ("seed", "mnemonic", "private_key", "secret_key", "keypair")
    for model in (WalletAccount, WalletBalanceSnapshot, WithdrawalIntent, ProfitSweepEvent):
        for row in db.query(model).all():
            for col in row.__table__.columns.keys():
                value = str(getattr(row, col, "") or "").lower()
                assert not any(b in value for b in banned), f"{model.__name__}.{col} leaks key material"


# ----------------------------- Accounting -----------------------------


def test_sweep_does_not_create_realized_pnl(db, wallets):
    """Moving money between wallets is not trading profit."""
    ws.record_balance_snapshot(db, wallets["bot"].id, "SOL", 10_000_000_000, SOL_MINT)
    _closed_position(db, realized_pnl=100.0)
    ws.set_sweep_enabled(db, True, "op")
    ws.set_wallet_enabled(db, True, "op")
    before = db.query(AccountingEvent).filter_by(event_type="REALIZED_PNL").count()
    ws.evaluate_and_record_sweep(db, "op", "close-5", wallets["bot"].id, "SOL")
    after = db.query(AccountingEvent).filter_by(event_type="REALIZED_PNL").count()
    assert before == after