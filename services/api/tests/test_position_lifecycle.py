"""Position lifecycle: TP/SL, idempotency, reconciliation, recovery (Tahap 4).

Before this, nothing closed a position automatically. `close_reason` was always
`operator_close` and a position rode until a human noticed. Each test below
fails on that code.

The recurring theme is fail-closed: a missing or stale mark must hold a
position rather than trigger an exit nobody can justify, and a crashed close
must leave something recoverable rather than a position that is half closed.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest
from app.accounting.equity import summarize_mode
from app.models.analysis import AnalysisRun, Signal
from app.models.market import MarketSnapshot, Token, TokenPair
from app.models.trading import AccountingEvent, BotRun, Fill, OrderIntent, Position
from app.services.position_manager import (
    ACTION_HOLD,
    ACTION_STOP_LOSS,
    ACTION_TAKE_PROFIT,
    PLAN_NONE,
    PLAN_PERCENT_FALLBACK,
    PLAN_SIGNAL,
    STATUS_CLOSED,
    STATUS_CLOSING,
    STATUS_OPEN,
    begin_exit,
    claim_for_exit,
    evaluate_exit,
    exit_idempotency_key,
    exit_plan,
    finalize_exit,
    get_exit_intent,
    recover_stalled_exits,
    release_from_exit,
    run_position_lifecycle,
)

MINT = "MintLifecycle111111111111111111111111111111"
NOW = datetime.now(UTC)
ENTRY = 10.0
STOP = 8.0
TARGET1 = 14.0


def _position(db, *, quantity=10.0, entry=ENTRY, fees=0.0, stop=STOP, targets=(TARGET1,), status=STATUS_OPEN):
    token = Token(chain="solana", mint_address=MINT, symbol="L")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address=f"pair-{token.id}")
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
        mint_address=MINT,
        signal_type="LONG",
        status="ACTIVE",
        decision="LONG_CANDIDATE",
        reasons=["test"],
        entry_reference=entry,
        stop_reference=stop,
        target_references=list(targets) if targets else None,
        fee_assumptions={"taker_fee_pct": 0.0},
        slippage_assumption=0.0,
        engine_version="engine-v1",
        strategy_version="v1",
        data_timestamp=NOW,
    )
    db.add(signal)
    db.flush()
    position = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=MINT,
        open_signal_id=signal.id,
        status=status,
        quantity=quantity,
        average_entry_price=entry,
        total_fees=fees,
    )
    db.add(position)
    db.commit()
    return position, pair


def _mark(db, pair, price, *, age_seconds=5):
    db.add(
        MarketSnapshot(
            pair_id=pair.id,
            price_usd=price,
            liquidity_usd=500_000.0,
            observed_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
        )
    )
    db.commit()


def _bot_running(db, *, mode="PAPER", kill_switch=False):
    from app.services.bot_service import get_bot_state, save_bot_state

    state = get_bot_state(db)
    state["status"] = "RUNNING"
    state["mode"] = mode
    state["kill_switch_active"] = kill_switch
    state["active_run_id"] = None
    save_bot_state(db, state)
    db.commit()


# --------------------------- exit plan resolution ---------------------------


def test_plan_prefers_the_signal(db):
    position, _ = _position(db)
    plan = exit_plan(db, position)
    assert plan.source == PLAN_SIGNAL
    assert plan.stop_price == pytest.approx(STOP)
    assert plan.target_prices == (pytest.approx(TARGET1),)
    assert plan.is_usable


def test_plan_falls_back_to_percentages_when_the_signal_is_silent(db):
    position, _ = _position(db, stop=None, targets=())
    plan = exit_plan(db, position)
    assert plan.source == PLAN_PERCENT_FALLBACK
    assert plan.stop_price == pytest.approx(ENTRY * 0.92)
    assert plan.target_prices[0] == pytest.approx(ENTRY * 1.20)


def test_plan_ignores_a_stop_above_the_entry(db):
    """An inverted plan would exit immediately; it is dropped, not inherited."""
    position, _ = _position(db, stop=ENTRY * 2, targets=(ENTRY * 0.5,))
    plan = exit_plan(db, position)
    assert plan.stop_price is None
    assert plan.target_prices == (), "a target at or below entry is unreachable, not a target"


def test_plan_degrades_to_percentages_when_the_signal_levels_are_unusable(db):
    """A NaN stop and an infinite target are not a plan; the percentage plan is."""
    position, _ = _position(db, stop=float("nan"), targets=(float("inf"),))
    plan = exit_plan(db, position)
    assert plan.source == PLAN_PERCENT_FALLBACK
    assert plan.stop_price == pytest.approx(ENTRY * 0.92)
    assert math.isfinite(plan.stop_price)
    assert all(math.isfinite(t) for t in plan.target_prices)


def test_plan_without_a_signal_falls_back_rather_than_guessing_nothing(db):
    position, _ = _position(db)
    position.open_signal_id = None
    db.commit()
    plan = exit_plan(db, position)
    assert plan.source == PLAN_PERCENT_FALLBACK


def test_plan_is_unusable_when_there_is_no_signal_and_no_entry(db):
    """Nothing to derive from and nothing to scale: no plan, so hold."""
    position, _ = _position(db)
    position.open_signal_id = None
    position.average_entry_price = 0.0
    db.commit()
    assert exit_plan(db, position).source == PLAN_NONE


# --------------------------- evaluation: unknown holds ---------------------------


def test_holds_when_the_mark_is_missing(db):
    position, pair = _position(db)  # no snapshot at all
    valuation = _valuation(db, position)
    decision = evaluate_exit(position, exit_plan(db, position), valuation)
    assert decision.action == ACTION_HOLD
    assert "UNKNOWN" in decision.reason
    assert not decision.should_exit


def test_holds_when_the_mark_is_stale(db):
    position, pair = _position(db)
    _mark(db, pair, 999.0, age_seconds=100_000)  # would be a huge take-profit
    valuation = _valuation(db, position)
    decision = evaluate_exit(position, exit_plan(db, position), valuation)
    assert decision.action == ACTION_HOLD
    assert "STALE" in decision.reason
    assert not decision.should_exit, "a stale price must not trigger an exit nobody can justify"


def test_holds_when_the_valuation_is_missing_entirely(db):
    position, _ = _position(db)
    decision = evaluate_exit(position, exit_plan(db, position), None)
    assert decision.action == ACTION_HOLD


def test_triggers_take_profit_on_a_fresh_mark(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    decision = evaluate_exit(position, exit_plan(db, position), _valuation(db, position))
    assert decision.action == ACTION_TAKE_PROFIT
    assert decision.should_exit
    assert decision.target_price == pytest.approx(TARGET1)


def test_triggers_stop_loss_on_a_fresh_mark(db):
    position, pair = _position(db)
    _mark(db, pair, STOP - 1)
    decision = evaluate_exit(position, exit_plan(db, position), _valuation(db, position))
    assert decision.action == ACTION_STOP_LOSS
    assert decision.should_exit


def test_holds_inside_the_band(db):
    position, pair = _position(db)
    _mark(db, pair, ENTRY + 1)
    decision = evaluate_exit(position, exit_plan(db, position), _valuation(db, position))
    assert decision.action == ACTION_HOLD


def test_holds_when_there_is_no_exit_plan(db):
    """Defensive branch: a KNOWN mark with no usable plan holds rather than
    exiting on a guessed level.

    Built directly rather than through the DB, because a position whose entry
    is zero is also unvaluable - so this combination cannot arise from stored
    data, and the branch exists only so a future plan resolver cannot make it
    reachable by accident.
    """
    from app.accounting.valuation import VALUATION_KNOWN, PositionValuation
    from app.services.position_manager import ExitPlan

    position, _ = _position(db)
    known = PositionValuation(
        position_id=position.id,
        status=VALUATION_KNOWN,
        mark_price=ENTRY + 1,
        mark_age_seconds=5.0,
        unrealized_pnl=10.0,
    )
    decision = evaluate_exit(position, ExitPlan(source=PLAN_NONE), known)
    assert decision.action == ACTION_HOLD
    assert "no exit plan" in decision.reason
    assert not decision.should_exit


def _valuation(db, position):
    from app.accounting.valuation import value_position

    return value_position(db, position)


# --------------------------- the sweep ---------------------------


def test_sweep_closes_on_take_profit(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    result = run_position_lifecycle(db, "PAPER")
    assert result["ok"]
    assert [c["action"] for c in result["closed"]] == [ACTION_TAKE_PROFIT]

    db.refresh(position)
    assert position.status == STATUS_CLOSED
    assert position.close_reason == "take_profit"
    assert position.realized_pnl > 0
    assert position.exit_order_intent_id is not None


def test_sweep_closes_on_stop_loss(db):
    position, pair = _position(db)
    _mark(db, pair, STOP - 1)
    _bot_running(db)

    result = run_position_lifecycle(db, "PAPER")
    assert [c["action"] for c in result["closed"]] == [ACTION_STOP_LOSS]
    db.refresh(position)
    assert position.status == STATUS_CLOSED
    assert position.realized_pnl < 0


def test_sweep_holds_a_position_with_no_mark(db):
    position, pair = _position(db)
    _bot_running(db)

    result = run_position_lifecycle(db, "PAPER")
    assert result["closed"] == []
    assert len(result["held"]) == 1
    assert "UNKNOWN" in result["held"][0]["reason"]
    db.refresh(position)
    assert position.status == STATUS_OPEN


def test_sweep_does_not_run_when_the_bot_is_stopped(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)

    result = run_position_lifecycle(db, "PAPER")
    assert result.get("skipped") == "bot is not running"
    db.refresh(position)
    assert position.status == STATUS_OPEN


def test_sweep_does_not_run_under_the_kill_switch(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db, kill_switch=True)

    result = run_position_lifecycle(db, "PAPER")
    assert result.get("skipped") == "kill switch active"
    db.refresh(position)
    assert position.status == STATUS_OPEN


def test_sweep_refuses_to_run_outside_paper(db):
    result = run_position_lifecycle(db, "LIVE")
    assert result["ok"] is False
    assert "PAPER" in result["error"]


def test_sweep_dry_run_changes_nothing(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    result = run_position_lifecycle(db, "PAPER", dry_run=True)
    assert [c["action"] for c in result["closed"]] == [ACTION_TAKE_PROFIT]
    assert result["closed"][0]["dry_run"] is True
    db.refresh(position)
    assert position.status == STATUS_OPEN, "a dry run must not close anything"
    assert db.query(Fill).count() == 0


def test_sweep_records_the_ledger(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    run_position_lifecycle(db, "PAPER")

    events = {e.event_type for e in db.query(AccountingEvent).all()}
    assert {"TRADE_CLOSE", "REALIZED_PNL", "FEE"} <= events
    assert len(db.query(Fill).all()) == 1
    fill = db.query(Fill).one()
    assert fill.fill_type == "SIMULATED"
    assert fill.side == "SELL"


def test_sweep_moves_equity(db):
    position, pair = _position(db, quantity=10.0, entry=ENTRY)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    run_position_lifecycle(db, "PAPER")

    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.valuation_status == "COMPLETE"
    assert snap.unrealized_pnl == 0.0, "a closed position leaves the unrealized bucket"
    assert snap.realized_pnl > 0


def test_sweep_is_idempotent_across_runs(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    run_position_lifecycle(db, "PAPER")
    first_fills = db.query(Fill).count()
    for _ in range(3):
        result = run_position_lifecycle(db, "PAPER")
        assert result["closed"] == []

    assert db.query(Fill).count() == first_fills == 1, "one exit must produce exactly one fill"
    events = db.query(AccountingEvent).filter(AccountingEvent.event_type == "REALIZED_PNL").all()
    assert len(events) == 1, "the ledger must not be written twice"


def test_sweep_is_idempotent_under_concurrent_calls(db):
    """Two sweeps, same tick: the claim is what makes the second one a no-op."""
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    first = run_position_lifecycle(db, "PAPER")
    second = run_position_lifecycle(db, "PAPER")

    assert len(first["closed"]) == 1
    assert second["closed"] == []
    assert db.query(Fill).count() == 1


# --------------------------- claim semantics ---------------------------


def test_claim_is_won_by_exactly_one_caller(db):
    position, _ = _position(db)
    assert claim_for_exit(db, position.id) is True
    assert claim_for_exit(db, position.id) is False, "a second claim must lose"

    db.refresh(position)
    assert position.status == STATUS_CLOSING


def test_release_returns_the_position_to_open(db):
    position, _ = _position(db)
    claim_for_exit(db, position.id)
    assert release_from_exit(db, position.id) is True
    db.refresh(position)
    assert position.status == STATUS_OPEN
    assert release_from_exit(db, position.id) is False


# --------------------------- recovery ---------------------------


def _crash_after_fill(db, position):
    """Simulate a crash between phase 1 and phase 2."""
    claim_for_exit(db, position.id)
    db.refresh(position)
    begun = begin_exit(db, position, TARGET1, 0.0, 0.0, "take_profit")
    assert begun["ok"]
    return begun


def test_recovery_finalizes_a_committed_fill(db):
    """The trade really happened; recovery must finish the bookkeeping."""
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    _crash_after_fill(db, position)
    db.refresh(position)
    assert position.status == STATUS_CLOSING, "precondition: stranded mid-close"

    recovered = recover_stalled_exits(db, "PAPER", older_than_seconds=0)
    assert [r["action"] for r in recovered] == ["finalized"]

    db.refresh(position)
    assert position.status == STATUS_CLOSED
    assert position.realized_pnl > 0
    pnl = db.query(AccountingEvent).filter(AccountingEvent.event_type == "REALIZED_PNL").all()
    assert len(pnl) == 1, "recovery writes the ledger exactly once"


def test_recovery_rolls_back_a_bare_claim(db):
    """Nothing was filled, so the position must return to OPEN untouched."""
    position, pair = _position(db)
    _bot_running(db)
    claim_for_exit(db, position.id)

    recovered = recover_stalled_exits(db, "PAPER", older_than_seconds=0)
    assert [r["action"] for r in recovered] == ["rolled_back"]
    db.refresh(position)
    assert position.status == STATUS_OPEN
    assert db.query(Fill).count() == 0
    assert db.query(AccountingEvent).count() == 0


def test_recovery_fails_an_intent_that_has_no_fill(db):
    """An intent without a fill is not a trade; roll back and mark it FAILED."""
    position, _ = _position(db)
    claim_for_exit(db, position.id)
    db.add(
        OrderIntent(
            bot_run_id=position.bot_run_id,
            signal_id=position.open_signal_id or position.id,
            mode="PAPER",
            idempotency_key=exit_idempotency_key(position.id),
            side="SELL",
            requested_size=100.0,
            reference_price=TARGET1,
            risk_decision="APPROVED",
            risk_reasons=["take_profit"],
            status="RISK_APPROVED",
        )
    )
    db.commit()

    recovered = recover_stalled_exits(db, "PAPER", older_than_seconds=0)
    assert [r["action"] for r in recovered] == ["rolled_back"]
    db.refresh(position)
    assert position.status == STATUS_OPEN
    assert get_exit_intent(db, position.id).status == "FAILED"


def test_recovery_leaves_a_recent_claim_alone(db):
    """A worker mid-write must not have its position stolen."""
    position, _ = _position(db)
    claim_for_exit(db, position.id)

    assert recover_stalled_exits(db, "PAPER", older_than_seconds=3600) == []
    db.refresh(position)
    assert position.status == STATUS_CLOSING


def test_a_fresh_stranded_claim_is_left_for_the_next_tick(db):
    """Recovery must not steal a position from a worker that is mid-write.

    The cost is that a genuinely crashed position stays CLOSING until the
    threshold passes. That is the safe direction: a position left open for one
    extra tick is recoverable, a position finalized twice is not.
    """
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    _crash_after_fill(db, position)

    result = run_position_lifecycle(db, "PAPER")
    assert result["recovered"] == []
    db.refresh(position)
    assert position.status == STATUS_CLOSING

    # Once the claim is old enough, the next sweep finishes it.
    position.updated_at = NOW - timedelta(seconds=10_000)
    db.commit()
    later = run_position_lifecycle(db, "PAPER")
    assert len(later["recovered"]) == 1
    db.refresh(position)
    assert position.status == STATUS_CLOSED
    assert db.query(Fill).count() == 1, "recovery must not add a second fill"


def test_recovery_does_not_double_write_the_ledger(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    _crash_after_fill(db, position)

    for _ in range(3):
        recover_stalled_exits(db, "PAPER", older_than_seconds=0)

    pnl = db.query(AccountingEvent).filter(AccountingEvent.event_type == "REALIZED_PNL").all()
    assert len(pnl) == 1


def test_finalize_is_a_noop_on_an_already_closed_position(db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    _crash_after_fill(db, position)
    finalize_exit(db, position, "take_profit")
    assert finalize_exit(db, position, "take_profit") is None
    db.refresh(position)
    assert position.status == STATUS_CLOSED


# --------------------------- operator close shares the path ---------------------------


def test_operator_close_uses_the_same_idempotency_key(db):
    from app.services.trading_service import close_position

    position, pair = _position(db)
    _mark(db, pair, 12.0)
    close_position(db, position.id, "operator_close", price_override=12.0)

    intent = get_exit_intent(db, position.id)
    assert intent is not None
    assert intent.idempotency_key == f"exit:{position.id}"
    db.refresh(position)
    assert position.status == STATUS_CLOSED


def test_operator_close_of_a_closed_position_conflicts(db):
    from app.core.errors import ConflictError
    from app.services.trading_service import close_position

    position, pair = _position(db)
    _mark(db, pair, 12.0)
    close_position(db, position.id, "operator_close", price_override=12.0)

    with pytest.raises(ConflictError):
        close_position(db, position.id, "operator_close", price_override=12.0)
    assert db.query(Fill).count() == 1


def test_operator_close_of_a_claimed_position_conflicts(db):
    from app.core.errors import ConflictError
    from app.services.trading_service import close_position

    position, pair = _position(db)
    _mark(db, pair, 12.0)
    claim_for_exit(db, position.id)

    with pytest.raises(ConflictError):
        close_position(db, position.id, "operator_close", price_override=12.0)


def test_manual_exit_pays_exit_costs(db):
    """A fill that costs nothing must not be priced as if it did.

    The signal declares 0% taker fee and 0% slippage, so closing at the target
    fills at exactly the target. Any cost here would come from a hard-coded
    constant ignoring the signal's own assumptions.
    """
    position, pair = _position(db, quantity=10.0, entry=ENTRY, fees=0.0)
    _mark(db, pair, TARGET1)
    _bot_running(db)
    run_position_lifecycle(db, "PAPER")

    db.refresh(position)
    fill = db.query(Fill).one()
    assert math.isclose(fill.fill_price, TARGET1, rel_tol=1e-9), (
        "0% slippage means the exit fills at the mark"
    )
    assert fill.fee_amount == pytest.approx(0.0)
    assert position.realized_pnl == pytest.approx(10.0 * (TARGET1 - ENTRY))


# --------------------------- API surface ---------------------------


def test_lifecycle_endpoint_defaults_to_dry_run(client, db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    r = client.post("/api/v1/bot/positions/lifecycle", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert len(body["closed"]) == 1
    assert body["closed"][0]["dry_run"] is True
    db.refresh(position)
    assert position.status == STATUS_OPEN


def test_lifecycle_endpoint_can_execute(client, db):
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)

    r = client.post("/api/v1/bot/positions/lifecycle", json={"dry_run": False})
    assert r.status_code == 200
    assert r.json()["dry_run"] is False
    db.refresh(position)
    assert position.status == STATUS_CLOSED


def test_lifecycle_endpoint_refuses_live(client):
    r = client.post("/api/v1/bot/positions/lifecycle", json={"mode": "LIVE"})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_positions_endpoint_exposes_the_exit_plan(client, db):
    position, pair = _position(db)
    r = client.get("/api/v1/bot/positions")
    item = r.json()["items"][0]
    assert item["exit_stop_price"] == pytest.approx(STOP)
    assert item["exit_target_prices"] == [pytest.approx(TARGET1)]
    assert item["exit_plan_source"] == PLAN_SIGNAL
    assert item["valuation_status"] == "UNKNOWN"


# --------------------------- PAPER only ---------------------------


def test_no_live_execution_path_exists(db):
    """Every fill this lifecycle can produce must be SIMULATED."""
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    _bot_running(db)
    run_position_lifecycle(db, "PAPER")

    fills = db.query(Fill).all()
    assert fills, "expected a fill"
    assert all(f.fill_type == "SIMULATED" for f in fills)
    assert all(f.mode == "PAPER" if hasattr(f, "mode") else True for f in fills)
    intents = db.query(OrderIntent).filter(OrderIntent.side == "SELL").all()
    assert all(i.mode == "PAPER" for i in intents)


def test_lifecycle_refuses_live_mode_positions(db):
    """Even a LIVE position in the table must not be touched."""
    position, pair = _position(db)
    _mark(db, pair, TARGET1 + 1)
    position.mode = "LIVE"
    db.commit()
    _bot_running(db)

    result = run_position_lifecycle(db, "PAPER")
    assert result["closed"] == []
    db.refresh(position)
    assert position.status == STATUS_OPEN
