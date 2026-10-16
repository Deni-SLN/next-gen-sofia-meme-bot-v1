"""Wallet balances, automatic sweep trigger, and alerts (Tahap 5).

The three gaps this file closes, each of which was reachable only from tests
before:

1. `record_balance_snapshot` had no producer, so `GET /wallets/{id}/balances`
   could answer only `UNAVAILABLE` and the sweep refused every action - which
   meant PRD v1.1's automatic mode could not be exercised at all.
2. `evaluate_and_record_sweep` had no trigger, so automatic 50% sweep never ran.
3. `AlertDelivery` was a table nobody wrote to, and the Telegram settings were
   declared, redacted and documented, then never read.

The recurring assertion is that unknown never becomes zero: a failed chain
read records UNKNOWN, an unknown balance blocks the sweep, and an unconfigured
channel records SKIPPED rather than pretending to have delivered.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.errors import ProviderError
from app.models.ops import AlertDelivery
from app.models.wallet import WalletAccount, WalletBalanceSnapshot, WalletPolicyVersion
from app.services import alert_service
from app.services import wallet_service as ws
from app.services.wallet_balance_service import (
    STATUS_UNKNOWN,
    USDC_MINT,
    WSOL_MINT,
    BalanceRead,
    asset_mint,
    persist_reads,
    refresh_wallet_balances,
)

NOW = datetime.now(UTC)


# --------------------------- fakes ---------------------------


class FakeRpc:
    """Stands in for the RPC provider. Never touches the network."""

    def __init__(self, sol=None, token=None, fail=False):
        self.sol = sol
        self.token = token
        self.fail = fail
        self.calls: list[str] = []

    async def get_sol_balance_lamports(self, owner, commitment="confirmed"):
        self.calls.append("sol")
        if self.fail:
            raise ProviderError("fake", "rpc down")
        if self.sol is None:
            raise ProviderError("fake", "no result")
        return self.sol

    async def get_token_balance_atomic(self, owner, mint, commitment="confirmed"):
        self.calls.append(f"token:{mint}")
        if self.fail:
            raise ProviderError("fake", "rpc down")
        if self.token is None:
            raise ProviderError("fake", "no result")
        return self.token


def _wallets(db):
    bot = WalletAccount(
        wallet_role="BOT", chain="solana", public_address="BotAddr111111111111111111111111111111"
    )
    main = WalletAccount(
        wallet_role="MAIN",
        chain="solana",
        public_address="MainAddr1111111111111111111111111111111",
        is_allowlisted=1,
    )
    cold = WalletAccount(
        wallet_role="MAIN",
        chain="solana",
        public_address="ColdAddr11111111111111111111111111111111",
        is_allowlisted=1,
    )
    db.add_all([bot, main, cold])
    db.commit()
    return bot, main


def _destination(db) -> WalletAccount:
    """The allowlisted MAIN wallet a transfer must be addressed to.

    Selected by address, not by ordering: the fixtures share a `created_at`,
    so a "newest" query is ambiguous and could return the source wallet.
    """
    return db.query(WalletAccount).filter(
        WalletAccount.public_address == "ColdAddr11111111111111111111111111111111"
    ).one()


# --------------------------- balance production ---------------------------


def test_balance_reads_come_from_the_chain(db):
    bot, _ = _wallets(db)
    rpc = FakeRpc(sol=2_000_000_000, token=25_000_000)
    reads = refresh_wallet_balances(db, provider=rpc)
    assert reads["ok"] == 4 and reads["unknown"] == 0

    snaps = db.query(WalletBalanceSnapshot).all()
    assert {s.asset for s in snaps} == {"SOL", "USDC"}
    sol = [s for s in snaps if s.asset == "SOL"][0]
    assert sol.balance_atomic == 2_000_000_000
    assert sol.status == "OK"
    assert rpc.calls  # the chain was actually consulted


def test_failed_read_records_unknown_not_zero(db):
    """The core rule: an unreadable balance is not a balance of zero."""
    bot, _ = _wallets(db)
    refresh_wallet_balances(db, provider=FakeRpc(fail=True))

    snaps = db.query(WalletBalanceSnapshot).all()
    assert snaps, "a failure must still leave an audit trail"
    assert all(s.status == STATUS_UNKNOWN for s in snaps)
    assert all(s.balance_atomic == 0 for s in snaps), "schema needs an int; status qualifies it"


def test_unknown_snapshot_is_never_returned_as_a_usable_balance(db):
    """A spending path must see None, not the stored zero."""
    bot, _ = _wallets(db)
    refresh_wallet_balances(db, provider=FakeRpc(fail=True))

    # The display path can still distinguish the two cases.
    display = ws.latest_snapshot(db, bot.id, "SOL", require_ok=False)
    assert display is not None
    assert display.status == STATUS_UNKNOWN

    # Every path that spends sees nothing usable.
    assert ws.latest_snapshot(db, bot.id, "SOL") is None
    evaluation = ws.evaluate_sweep(db, bot.id, "SOL")
    assert evaluation.sweepable_atomic == 0
    assert any("UNKNOWN" in r for r in evaluation.reasons), evaluation.reasons


def test_a_genuine_zero_balance_is_still_readable(db):
    """A wallet that really holds zero must not be confused with 'unknown'."""
    bot, _ = _wallets(db)
    refresh_wallet_balances(db, provider=FakeRpc(sol=0, token=0))

    snap = ws.latest_snapshot(db, bot.id, "SOL")
    assert snap is not None
    assert snap.status == "OK"
    assert snap.balance_atomic == 0


def test_balances_endpoint_distinguishes_unknown_from_unavailable(client, db, monkeypatch):
    import app.services.wallet_balance_service as balance_service

    monkeypatch.setattr(balance_service, "SolanaRPCProvider", lambda *a, **k: FakeRpc(fail=True))
    _bot, main = _wallets(db)
    client.post("/api/v1/wallets/balances/refresh")

    body = client.get(f"/api/v1/wallets/{main.id}/balances").json()
    assert {i["status"] for i in body["items"]} == {"UNKNOWN"}, (
        "a failed read must not be reported as OK"
    )


def test_one_asset_failing_does_not_erase_the_other(db):
    bot, _ = _wallets(db)

    class HalfBroken(FakeRpc):
        async def get_token_balance_atomic(self, owner, mint, commitment="confirmed"):
            raise ProviderError("fake", "token account unavailable")

    summary = refresh_wallet_balances(db, provider=HalfBroken(sol=5_000_000))
    assert summary["ok"] == 2, "SOL still reads for both wallets"
    assert summary["unknown"] == 2, "USDC failed for both wallets"

    ok = [s for s in db.query(WalletBalanceSnapshot).all() if s.asset == "SOL"]
    assert all(s.status == "OK" and s.balance_atomic == 5_000_000 for s in ok)


def test_sol_spendable_excludes_the_rent_buffer(db):
    bot, _ = _wallets(db)
    refresh_wallet_balances(db, provider=FakeRpc(sol=1_000_000, token=0))
    snap = ws.latest_snapshot(db, bot.id, "SOL")
    assert snap.balance_atomic == 1_000_000
    assert snap.spendable_atomic == 1_000_000 - 5_000


def test_assets_have_the_right_mints():
    assert asset_mint("SOL") == WSOL_MINT
    assert asset_mint("USDC") == USDC_MINT
    with pytest.raises(ProviderError):
        asset_mint("BTC")


def test_balances_endpoint_records_reads_over_http(client, db, monkeypatch):
    """The refresh endpoint must produce real snapshot rows.

    The provider is stubbed: this test is about the wiring, not the chain, and
    must not make a network call.
    """
    import app.services.wallet_balance_service as balance_service

    monkeypatch.setattr(balance_service, "SolanaRPCProvider", lambda *a, **k: FakeRpc(sol=3_000_000, token=7_000_000))
    _bot, main = _wallets(db)

    r = client.post("/api/v1/wallets/balances/refresh")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] >= 2

    body = client.get(f"/api/v1/wallets/{main.id}/balances").json()
    assert len(body["items"]) == 2
    # No provider is reachable here, so a real read would be UNKNOWN. What this
    # proves is that the endpoint writes snapshots at all - before Tahap 5 it
    # could only ever answer UNAVAILABLE.
    assert db.query(WalletBalanceSnapshot).count() >= 4


def test_balances_endpoint_reports_unknown_when_the_chain_is_unreachable(client, db, monkeypatch):
    import app.services.wallet_balance_service as balance_service

    monkeypatch.setattr(balance_service, "SolanaRPCProvider", lambda *a, **k: FakeRpc(fail=True))
    _bot, main = _wallets(db)

    summary = client.post("/api/v1/wallets/balances/refresh").json()
    assert summary["unknown"] >= 2
    assert summary["ok"] == 0


def test_balances_endpoint_is_null_when_nothing_was_ever_read(client, db):
    _bot, main = _wallets(db)
    body = client.get(f"/api/v1/wallets/{main.id}/balances").json()
    for item in body["items"]:
        assert item["status"] == "UNAVAILABLE"
        assert item["balance_atomic"] is None, "no data is null, not zero"


# --------------------------- automatic sweep trigger ---------------------------


def _closed_profit(db, *, realized=100.0, status="CLOSED"):
    """A closed position, which is what should trigger a sweep offer."""
    from app.models.market import Token, TokenPair
    from app.models.trading import BotRun, Position

    token = db.query(Token).first() or Token(chain="solana", mint_address="MintSweep11111111111111111111111111111")
    db.add(token)
    db.flush()
    pair = db.query(TokenPair).first() or TokenPair(token_id=token.id, pair_address="pair-sw")
    db.add(pair)
    db.flush()
    run = db.query(BotRun).first() or BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    position = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=token.mint_address,
        status=status,
        quantity=10.0,
        average_entry_price=10.0,
        total_fees=0.0,
        realized_pnl=realized,
    )
    db.add(position)
    db.commit()
    return position


def test_closing_a_profit_offers_a_sweep(db):
    """The trigger that did not exist before Tahap 5."""
    from app.models.wallet import ProfitSweepEvent

    _bot, main = _wallets(db)
    position = _closed_profit(db, realized=100.0)
    ws.record_balance_snapshot(db, main.id, "USDC", 1_000_000, USDC_MINT)
    ws.set_sweep_enabled(db, True, "test")

    from app.services.position_manager import _offer_profit_sweep

    _offer_profit_sweep(db, position, 100.0)

    events = db.query(ProfitSweepEvent).all()
    assert events, "a profitable close must be offered to the sweep evaluator"
    assert {e.asset for e in events} == {"SOL", "USDC"}


def test_the_sweep_trigger_is_idempotent(db):
    from app.models.wallet import ProfitSweepEvent
    from app.services.position_manager import _offer_profit_sweep

    _bot, main = _wallets(db)
    position = _closed_profit(db, realized=100.0)
    ws.record_balance_snapshot(db, main.id, "USDC", 1_000_000, USDC_MINT)
    ws.set_sweep_enabled(db, True, "test")

    for _ in range(3):
        _offer_profit_sweep(db, position, 100.0)

    usdc = [e for e in db.query(ProfitSweepEvent).all() if e.asset == "USDC"]
    assert len(usdc) == 1, "one close must produce one sweep event per asset"


def test_closing_a_profit_through_the_lifecycle_records_a_sweep(db):
    """End-to-end: TP/SL close -> ledger -> sweep offer.

    The other sweep tests call the trigger directly, which would still pass if
    the trigger were never wired into `finalize_exit`. This one goes through
    the real close path, so removing the wiring fails here.
    """
    from app.models.market import MarketSnapshot
    from app.models.wallet import ProfitSweepEvent
    from app.services.bot_service import get_bot_state, save_bot_state
    from app.services.position_manager import run_position_lifecycle

    bot, main = _wallets(db)
    position, pair = _position(db, entry=10.0, quantity=10.0, stop=8.0, targets=(14.0,))
    db.add(
        MarketSnapshot(
            pair_id=pair.id,
            price_usd=15.0,
            liquidity_usd=500_000.0,
            observed_at=datetime.now(UTC) - timedelta(seconds=5),
        )
    )
    ws.record_balance_snapshot(db, main.id, "USDC", 1_000_000, USDC_MINT)
    ws.set_sweep_enabled(db, True, "test")
    state = get_bot_state(db)
    state["status"] = "RUNNING"
    state["mode"] = "PAPER"
    save_bot_state(db, state)
    db.commit()

    result = run_position_lifecycle(db, "PAPER")
    assert result["closed"], f"expected a take-profit close: {result}"
    db.refresh(position)
    assert position.status == "CLOSED"
    assert position.realized_pnl > 0

    events = db.query(ProfitSweepEvent).all()
    assert events, "closing a profit must offer it to the sweep, not stop at the ledger"
    assert {e.asset for e in events} == {"SOL", "USDC"}


def _position(db, *, quantity=10.0, entry=10.0, fees=0.0, stop=8.0, targets=(14.0,)):
    """An OPEN position with a signal carrying an explicit exit plan."""
    from app.models.analysis import AnalysisRun, Signal
    from app.models.market import Token, TokenPair
    from app.models.trading import BotRun, Position

    token = Token(chain="solana", mint_address="MintSweepPos111111111111111111111111111111")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="pair-sweep-pos")
    db.add(pair)
    db.flush()
    run = BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    analysis = AnalysisRun(
        token_id=token.id,
        pair_id=pair.id,
        engine_version="engine-v1",
        scoring_config_version="scoring-v1",
        decision="LONG_CANDIDATE",
        reasons=["test"],
        input_snapshot={},
        provider_versions={},
    )
    db.add(analysis)
    db.flush()
    signal = Signal(
        analysis_run_id=analysis.id,
        token_id=token.id,
        pair_id=pair.id,
        mint_address=token.mint_address,
        signal_type="LONG",
        status="ACTIVE",
        decision="LONG_CANDIDATE",
        reasons=["test"],
        entry_reference=entry,
        stop_reference=stop,
        target_references=list(targets),
        fee_assumptions={"taker_fee_pct": 0.0},
        slippage_assumption=0.0,
        engine_version="engine-v1",
        strategy_version="v1",
        data_timestamp=datetime.now(UTC),
    )
    db.add(signal)
    db.flush()
    position = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=token.mint_address,
        open_signal_id=signal.id,
        status="OPEN",
        quantity=quantity,
        average_entry_price=entry,
        total_fees=fees,
    )
    db.add(position)
    db.commit()
    return position, pair


def test_a_loss_is_never_offered_for_sweep(db):
    from app.models.wallet import ProfitSweepEvent
    from app.services.position_manager import _offer_profit_sweep

    _bot, main = _wallets(db)
    position = _closed_profit(db, realized=-50.0)
    _offer_profit_sweep(db, position, -50.0)
    assert db.query(ProfitSweepEvent).count() == 0


def test_sweep_is_recorded_as_skipped_while_the_gate_is_off(db):
    """The gate being off must leave a record, not silence."""
    from app.models.wallet import ProfitSweepEvent
    from app.services.position_manager import _offer_profit_sweep

    _bot, main = _wallets(db)
    position = _closed_profit(db, realized=100.0)
    ws.record_balance_snapshot(db, main.id, "USDC", 1_000_000, USDC_MINT)
    ws.set_sweep_enabled(db, False, "test")

    _offer_profit_sweep(db, position, 100.0)

    events = db.query(ProfitSweepEvent).all()
    assert events, "the attempt itself must be recorded"
    assert all(e.status == "SKIPPED" for e in events)
    assert all(e.sweep_amount_atomic == 0 for e in events)
    assert all(e.withdrawal_intent_id is None for e in events), (
        "no intent may exist when the gate is off"
    )


def test_sweep_is_skipped_without_a_fresh_balance(db):
    """No usable balance -> no sweep, and the reason says so."""
    _bot, main = _wallets(db)
    _closed_profit(db, realized=100.0)
    evaluation = ws.evaluate_sweep(db, main.id, "USDC")
    assert evaluation.sweepable_atomic == 0
    assert any("balance" in r.lower() or "unavailable" in r.lower() for r in evaluation.reasons)


def test_sweep_is_skipped_when_the_only_balance_is_unknown(db):
    _bot, main = _wallets(db)
    _closed_profit(db, realized=100.0)
    persist_reads(
        db,
        [BalanceRead(wallet_id=main.id, asset="USDC", ok=False, reason="rpc down")],
    )
    evaluation = ws.evaluate_sweep(db, main.id, "USDC")
    assert evaluation.sweepable_atomic == 0


def test_dynamic_reserve_never_goes_below_the_operational_buffer(db):
    _bot, main = _wallets(db)
    ws.record_balance_snapshot(db, main.id, "SOL", 1_000_000, WSOL_MINT)
    reserve = ws.compute_dynamic_reserve(db, main.id, "SOL")
    assert reserve.operational_buffer_atomic > 0
    assert reserve.total_atomic >= reserve.operational_buffer_atomic


def test_live_transfer_gate_stays_off(db):
    """Reaching READY_TO_SIGN must be impossible without the on-chain gate."""
    from app.core.errors import ForbiddenError

    _bot, main = _wallets(db)
    dest = _destination(db)
    ws.record_balance_snapshot(db, main.id, "SOL", 10_000_000, WSOL_MINT)
    intent = ws.create_withdrawal_intent(
        db, "operator", main.id, "SOL", 1_000_000, "gate-test-1",
        trigger_type="MANUAL", destination_wallet_id=dest.id,
    )
    intent_id = intent["intent"]["id"]

    assert ws.is_wallet_enabled(db) is False
    with pytest.raises(ForbiddenError):
        ws.transition_intent(db, intent_id, "operator", "READY_TO_SIGN")


def test_opening_the_gate_does_not_skip_validation(db):
    """With the gate on and a real balance, validation still runs every check."""
    _bot, main = _wallets(db)
    dest = _destination(db)

    # Gate on, but no balance was ever read.
    ws.set_wallet_enabled(db, True, "operator")
    report = ws.validate_transfer(
        db,
        source_wallet_id=main.id,
        destination_wallet_id=dest.id,
        asset="SOL",
        amount_atomic=1_000_000,
    )
    assert report["valid"] is False
    assert report["wallet_onchain_gate_enabled"] is True
    assert "balance" in " ".join(report["failed_checks"]).lower()

    # Gate on, balance present, but the amount exceeds it.
    ws.record_balance_snapshot(db, main.id, "SOL", 100_000, WSOL_MINT)
    over = ws.validate_transfer(
        db,
        source_wallet_id=main.id,
        destination_wallet_id=dest.id,
        asset="SOL",
        amount_atomic=10_000_000,
    )
    assert over["valid"] is False


# --------------------------- alerts ---------------------------


def _alert(**over) -> alert_service.Alert:
    base = {
        "dedup_key": "test:key",
        "title": "Something happened",
        "body": "details",
        "severity": "warning",
    }
    base.update(over)
    return alert_service.Alert(**base)


def test_alert_is_recorded(db):
    result = alert_service.record_alert(db, _alert())
    assert result["recorded"] is True
    row = db.query(AlertDelivery).one()
    assert row.delivery_status == "PENDING"
    assert row.dedup_key == "test:key"


def test_alert_is_deduplicated_by_key(db):
    alert_service.record_alert(db, _alert())
    second = alert_service.record_alert(db, _alert(title="Again"))
    assert second["recorded"] is False
    assert second["reason"] == "duplicate dedup_key"
    assert db.query(AlertDelivery).count() == 1


def test_repeat_conditions_advance_the_bucket_to_refire(db):
    """A constant key could never fire twice: the unique index would reject it.

    Rules therefore bucket their keys, so an hour later the same condition
    produces a new key and the operator gets a reminder.
    """
    early = int(NOW.timestamp() // 3600)
    alert_service.record_alert(db, _alert(dedup_key=f"valuation:x:{early}"))
    later = NOW + timedelta(hours=2)
    alert_service.record_alert(db, _alert(dedup_key=f"valuation:x:{int(later.timestamp() // 3600)}"))
    assert db.query(AlertDelivery).count() == 2


def test_different_keys_both_fire(db):
    alert_service.record_alert(db, _alert(dedup_key="a"))
    alert_service.record_alert(db, _alert(dedup_key="b"))
    assert db.query(AlertDelivery).count() == 2


def test_unconfigured_telegram_is_skipped_not_failed(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")

    alert_service.record_alert(db, _alert())
    result = alert_service.flush_pending(db)
    assert result["skipped"] == 1
    assert result["sent"] == 0
    row = db.query(AlertDelivery).one()
    assert row.delivery_status == "SKIPPED"
    assert row.attempt_count == 1


def test_failed_delivery_is_recorded(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "secret-token-value")
    monkeypatch.setattr(settings, "telegram_chat_id", "12345")

    def _boom(alert, timeout=10.0):
        return {"ok": False, "reason": "network down"}

    monkeypatch.setattr(alert_service, "send_telegram", _boom)
    alert_service.record_alert(db, _alert())
    result = alert_service.flush_pending(db)
    assert result["failed"] == 1
    assert db.query(AlertDelivery).one().delivery_status == "FAILED"


def test_the_bot_token_never_appears_in_a_stored_alert(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "123456:SUPERSECRET")
    monkeypatch.setattr(settings, "telegram_chat_id", "999")

    def _capture(alert, timeout=10.0):
        assert "SUPERSECRET" not in alert.body
        assert "SUPERSECRET" not in alert.title
        return {"ok": False, "reason": "not sent (test)"}

    monkeypatch.setattr(alert_service, "send_telegram", _capture)
    alert_service.record_alert(db, _alert(body="balance went down"))
    alert_service.flush_pending(db)

    row = db.query(AlertDelivery).one()
    assert "SUPERSECRET" not in (row.body or "")
    assert "SUPERSECRET" not in (row.title or "")


def test_send_failure_does_not_raise(db, monkeypatch):
    """An alerting path must not be able to take down the job that raised it."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(settings, "telegram_chat_id", "1")

    import httpx

    def _raise(*a, **k):
        raise httpx.ConnectError("dns")

    monkeypatch.setattr(httpx, "post", _raise)
    result = alert_service.send_telegram(_alert())
    assert result["ok"] is False
    assert "dns" in result["reason"] or "ConnectError" in result["reason"]


def test_unvalued_position_raises_an_alert(db):
    from app.models.market import Token, TokenPair
    from app.models.trading import BotRun, Position

    token = Token(chain="solana", mint_address="MintAlert1111111111111111111111111111111")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="pair-al")
    db.add(pair)
    db.flush()
    run = BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    db.add(
        Position(
            bot_run_id=run.id,
            mode="PAPER",
            token_id=token.id,
            mint_address=token.mint_address,
            status="OPEN",
            quantity=1.0,
            average_entry_price=1.0,
            total_fees=0.0,
        )
    )
    db.commit()

    result = alert_service.evaluate_alert_rules(db)
    assert result["recorded"] >= 1
    body = db.query(AlertDelivery).one().body
    assert "not priced" in body.lower() or "usable mark" in body.lower()


def test_rules_do_nothing_on_a_healthy_book(db):
    result = alert_service.evaluate_alert_rules(db)
    assert result["recorded"] == 0


# --------------------------- API surface ---------------------------


def test_alerts_list_endpoint(client, db):
    alert_service.record_alert(db, _alert())
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["dedup_key"] == "test:key"
    assert body["telegram_configured"] is False


def test_alerts_evaluate_endpoint(client, db):
    r = client.post("/api/v1/alerts/evaluate")
    assert r.status_code == 200
    assert "fired" in r.json()


def test_alerts_flush_endpoint(client, db):
    alert_service.record_alert(db, _alert())
    r = client.post("/api/v1/alerts/flush")
    assert r.status_code == 200
    assert r.json()["skipped"] == 1


def test_alerts_deliver_unknown_id(client, db):
    r = client.post("/api/v1/alerts/does-not-exist/deliver")
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_wallet_pages_are_routed():
    from pathlib import Path

    web = Path(__file__).resolve().parents[3] / "apps" / "web" / "src"
    app = (web / "App.tsx").read_text(encoding="utf-8")
    layout = (web / "components" / "Layout.tsx").read_text(encoding="utf-8")
    assert "Wallet" in app and "Alerts" in app, "both pages must be routed"
    assert "/wallet" in layout and "/alerts" in layout, "both pages must be in the nav"
    assert (web / "pages" / "Wallet.tsx").exists()
    assert (web / "pages" / "Alerts.tsx").exists()


def test_policy_default_is_fifty_percent(db):
    policy = ws.default_policy(db)
    assert policy.sweep_percent == 50
    assert isinstance(policy, WalletPolicyVersion)
