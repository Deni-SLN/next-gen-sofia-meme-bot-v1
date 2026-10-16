"""Mark-to-market valuation regression (Tahap 1).

The defect these tests lock down: `Position.unrealized_pnl` existed as a column
and was summed into equity, but nothing ever wrote it. Every open position was
therefore worth exactly its cost basis in equity, HWM, drawdown and the risk
gate - a fabricated zero, rendered as a plausible number.

Each test below fails on the pre-fix code. None of them accepts a number that
was not measured: missing, stale, non-finite and non-positive prices must all
leave the valuation unknown, and unknown must reject at the risk gate.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest
from app.accounting.equity import summarize_mode
from app.accounting.valuation import (
    VALUATION_KNOWN,
    VALUATION_STALE,
    VALUATION_UNKNOWN,
    refresh_open_positions,
    unrealized_for,
    value_position,
)
from app.models.market import MarketSnapshot, Token, TokenPair
from app.models.trading import BotRun, Position

MINT = "So11111111111111111111111111111111111111112"
# Real clock: `summarize_mode` values positions against `datetime.now()` unless a
# time is passed explicitly, so snapshot timestamps must be relative to it.
NOW = datetime.now(UTC)


def _token_and_pair(db):
    token = Token(chain="solana", mint_address=MINT, symbol="T")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="pair-1")
    db.add(pair)
    db.commit()
    return token, pair


def _position(db, token, *, quantity=10.0, entry=2.0, fees=0.5, status="OPEN", taker_fee_pct=0.0):
    from app.models.analysis import AnalysisRun, Signal

    pair = db.query(TokenPair).filter(TokenPair.token_id == token.id).first()
    run = BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    analysis = AnalysisRun(
        token_id=token.id,
        pair_id=pair.id,
        engine_version="engine-v1",
        scoring_config_version="scoring-v1",
        score=80.0,
        coverage=1.0,
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
        risk_reward=2.0,
        coverage=1.0,
        risk_flags=[],
        engine_version="engine-v1",
        strategy_version="v1",
        fee_assumptions={"taker_fee_pct": taker_fee_pct},
        slippage_assumption=0.0,
        data_timestamp=NOW,
    )
    db.add(signal)
    db.flush()
    pos = Position(
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
    db.add(pos)
    db.commit()
    return pos


def _snapshot(db, pair, price, *, age_seconds=5):
    snap = MarketSnapshot(
        pair_id=pair.id,
        price_usd=price,
        liquidity_usd=500_000.0,
        observed_at=NOW - timedelta(seconds=age_seconds),
    )
    db.add(snap)
    db.commit()
    return snap


# --------------------------- the reported defect ---------------------------


def test_open_position_is_worth_more_than_cost_basis(db):
    """The core defect: a profitable open position must lift equity."""
    token, pair = _token_and_pair(db)
    pos = _position(db, token, quantity=10.0, entry=2.0, fees=0.5)
    _snapshot(db, pair, price=3.0)  # +10.0 gross, -0.5 entry fee

    snap = summarize_mode(db, "PAPER", 1000.0)

    assert snap.valuation_status == "COMPLETE"
    assert snap.unrealized_pnl == pytest.approx(9.5)
    assert snap.equity == pytest.approx(1009.5)
    # The row itself must carry the mark, not just the aggregate.
    db.refresh(pos)
    assert pos.valuation_status == VALUATION_KNOWN
    assert pos.unrealized_pnl == pytest.approx(9.5)
    assert pos.mark_price == 3.0


def test_losing_open_position_reduces_equity(db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=10.0, entry=5.0, fees=0.5)
    _snapshot(db, pair, price=4.0)

    snap = summarize_mode(db, "PAPER", 1000.0)

    assert snap.unrealized_pnl == pytest.approx(-10.5)
    assert snap.equity == pytest.approx(989.5)


def test_equity_uses_the_mark_not_the_entry(db):
    """Two positions at the same entry price must not be reported identically
    when their marks differ."""
    token_a, pair_a = _token_and_pair(db)
    _position(db, token_a, quantity=1.0, entry=10.0, fees=0.0)
    _snapshot(db, pair_a, price=20.0)

    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.unrealized_pnl == pytest.approx(10.0)


def test_entry_fees_reduce_unrealized(db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=1.0, entry=100.0, fees=3.0)
    _snapshot(db, pair, price=100.0)  # flat price

    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.unrealized_pnl == pytest.approx(-3.0), "a flat price is not free after entry fees"


def test_unrealized_converts_to_realized_without_a_jump(db):
    """Closing at the mark must produce the same PnL the valuation promised."""
    from app.services.trading_service import close_position

    token, pair = _token_and_pair(db)
    pos = _position(db, token, quantity=10.0, entry=2.0, fees=0.0)
    _snapshot(db, pair, price=3.0)
    before = summarize_mode(db, "PAPER", 1000.0)
    assert before.equity == pytest.approx(1010.0)

    # Zero slippage and fee so the exit price is exactly the mark.
    pos_id = pos.id
    close_position(db, pos_id, "operator_close", price_override=3.0)
    after = summarize_mode(db, "PAPER", 1000.0)
    assert after.equity == pytest.approx(1010.0, abs=1e-6)


# --------------------------- unknown never becomes zero ---------------------------


def test_missing_snapshot_is_unknown_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    # no snapshot at all

    snap = summarize_mode(db, "PAPER", 1000.0)

    assert snap.valuation_status == "INCOMPLETE"
    assert snap.unrealized_pnl is None
    assert snap.equity is None
    assert snap.current_drawdown_pct is None
    assert snap.unmarked_positions == 1


def test_no_pair_for_token_is_unknown(db):
    """A position whose token has no pair has no mark, and must not be worth 0."""
    token = Token(chain="solana", mint_address=MINT, symbol="T")
    db.add(token)
    db.flush()
    run = BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    pos = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=MINT,
        status="OPEN",
        quantity=1.0,
        average_entry_price=1.0,
        total_fees=0.0,
    )
    db.add(pos)
    db.commit()  # the token has no TokenPair at all

    valuation = value_position(db, pos, now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.reason == "no_pair_for_token"
    assert valuation.unrealized_pnl is None

    snap = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert snap.equity is None


def test_null_price_is_unknown_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=None)

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.reason == "snapshot_price_unreadable"
    assert valuation.unrealized_pnl is None


def test_nan_price_is_unknown_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=float("nan"))

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.unrealized_pnl is None


def test_infinite_price_is_unknown_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=float("inf"))

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.unrealized_pnl is None


def test_zero_price_is_unknown_not_zero(db):
    """A zero price is unreadable, not a total loss and not break-even."""
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=0.0)

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.reason == "snapshot_price_not_positive"


def test_negative_price_is_unknown_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=-2.0)

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.unrealized_pnl is None


def test_stale_price_is_stale_not_zero(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=50.0, age_seconds=100_000)

    valuation = value_position(db, db.query(Position).first(), now=NOW, max_age_seconds=300)

    assert valuation.status == VALUATION_STALE
    assert valuation.unrealized_pnl is None, "a stale mark must not be valued as if it were current"
    assert valuation.mark_price == 50.0, "the observed price is still reported as stale, not discarded"


def test_stale_price_makes_the_whole_book_unknown(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=3.0, age_seconds=100_000)

    snap = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert snap.valuation_status == "INCOMPLETE"
    assert snap.equity is None


def test_future_timestamp_is_stale(db):
    """Clock skew must not make an ancient snapshot look brand new."""
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=3.0, age_seconds=-50_000)

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_STALE
    assert valuation.unrealized_pnl is None


def test_snapshot_without_timestamp_is_unknown(db, monkeypatch):
    """`observed_at` is NOT NULL in the schema, so this covers the defensive path:
    a snapshot that reaches the valuation without a usable timestamp must not be
    treated as fresh."""
    import app.accounting.valuation as valuation_mod

    token, pair = _token_and_pair(db)
    _position(db, token)
    snap_row = _snapshot(db, pair, price=3.0)

    class Untimestamped:
        price_usd = 3.0
        observed_at = None

    monkeypatch.setattr(valuation_mod, "_latest_snapshot", lambda db, token_id: (Untimestamped(), None))

    valuation = value_position(db, db.query(Position).first(), now=NOW)
    assert valuation.status == VALUATION_UNKNOWN
    assert valuation.reason == "snapshot_has_no_timestamp"
    assert valuation.unrealized_pnl is None
    assert snap_row.observed_at is not None


def test_partial_book_reports_a_floor_but_not_a_total(db):
    """One valued + one unvalued position: the floor is visible, the total is not."""
    token_a, pair_a = _token_and_pair(db)
    _position(db, token_a, quantity=1.0, entry=1.0, fees=0.0)
    _snapshot(db, pair_a, price=11.0)  # +10.0

    token_b = Token(chain="solana", mint_address="OtherMint11111111111111111111111111111111", symbol="B")
    db.add(token_b)
    db.flush()
    pair_b = TokenPair(token_id=token_b.id, pair_address="pair-b")
    db.add(pair_b)
    db.commit()
    _position(db, token_b, quantity=1.0, entry=1.0, fees=0.0)  # pair exists, no snapshot yet

    snap = summarize_mode(db, "PAPER", 1000.0)

    assert snap.valuation_status == "INCOMPLETE"
    assert snap.unrealized_pnl is None
    assert snap.unmarked_positions == 1
    assert snap.known_unrealized_pnl == pytest.approx(10.0)
    assert snap.known_equity == pytest.approx(1010.0)


def test_a_previous_good_mark_does_not_survive_staleness(db):
    """Re-valuation must clear a stale number rather than leave it on the row."""
    token, pair = _token_and_pair(db)
    pos = _position(db, token, quantity=1.0, entry=1.0, fees=0.0)
    _snapshot(db, pair, price=11.0)
    refresh_open_positions(db, "PAPER", now=NOW)
    db.refresh(pos)
    assert pos.unrealized_pnl == pytest.approx(10.0)

    # Push the snapshot far into the past and re-value.
    snap_row = db.query(MarketSnapshot).first()
    snap_row.observed_at = NOW - timedelta(seconds=100_000)
    db.commit()
    refresh_open_positions(db, "PAPER", now=NOW)
    db.refresh(pos)

    assert pos.valuation_status == VALUATION_STALE
    assert pos.unrealized_pnl is None


def test_closed_positions_are_not_valued(db):
    token, pair = _token_and_pair(db)
    _position(db, token, status="CLOSED")
    _snapshot(db, pair, price=3.0)

    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.valuation_status == "COMPLETE"
    assert snap.unrealized_pnl == 0.0


def test_valuation_is_deterministic(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    _snapshot(db, pair, price=3.0)
    first = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    second = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert first.unrealized_pnl == second.unrealized_pnl
    assert first.equity == second.equity


# --------------------------- invalid position terms ---------------------------


@pytest.mark.parametrize(
    "quantity,entry",
    [
        (0.0, 2.0),
        (-1.0, 2.0),
        (10.0, 0.0),
        (10.0, -2.0),
        (float("nan"), 2.0),
        (10.0, float("inf")),
    ],
)
def test_invalid_position_terms_yield_no_pnl(quantity, entry):
    pos = Position(quantity=quantity, average_entry_price=entry, total_fees=0.0)
    assert unrealized_for(3.0, pos) is None


def test_non_finite_fees_yield_no_pnl():
    pos = Position(quantity=1.0, average_entry_price=1.0, total_fees=float("nan"))
    assert unrealized_for(3.0, pos) is None


@pytest.mark.parametrize("mark", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_invalid_marks_yield_no_pnl(mark):
    pos = Position(quantity=1.0, average_entry_price=1.0, total_fees=0.0)
    assert unrealized_for(mark, pos) is None


def test_unrealized_is_finite_for_extreme_marks():
    pos = Position(quantity=1e18, average_entry_price=1e-9, total_fees=0.0)
    value = unrealized_for(1e9, pos)
    assert value is None or math.isfinite(value)


# --------------------------- high-water mark and drawdown ---------------------------


def test_high_water_mark_tracks_unrealized_peaks(db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=1.0, entry=1.0, fees=0.0)
    _snapshot(db, pair, price=21.0)  # +20

    snap = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert snap.high_water_mark == pytest.approx(1020.0)


def test_drawdown_is_measured_against_a_realised_peak(db):
    """Peak from a closed trade, then an open loss: drawdown must be non-zero."""
    from app.accounting.equity import record_event

    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=200.0, idempotency_key="w")
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=1.0, entry=1.0, fees=0.0)
    _snapshot(db, pair, price=1.0)  # flat mark

    snap = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert snap.high_water_mark == pytest.approx(1200.0)
    assert snap.current_drawdown_pct == pytest.approx(0.0)

    # Push the mark down and the drawdown must appear.
    db.query(MarketSnapshot).first().price_usd = 0.5
    db.commit()
    down = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert down.current_drawdown_pct == pytest.approx((1200.0 - 1199.5) / 1200.0 * 100, abs=1e-6)
    assert down.current_drawdown_pct > 0


def test_unvalued_book_reports_no_drawdown_number(db):
    token, pair = _token_and_pair(db)
    _position(db, token)
    # no snapshot

    snap = summarize_mode(db, "PAPER", 1000.0, now=NOW)
    assert snap.current_drawdown_pct is None
    assert snap.high_water_mark == 1000.0, "the historical peak is still well defined"


# --------------------------- the API must not launder unknown into a number ---------------------------


def test_overview_returns_null_equity_for_an_unvalued_book(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token)  # no snapshot -> unvalued

    r = client.get("/api/v1/portfolio/overview")
    assert r.status_code == 200
    paper = r.json()["modes"]["PAPER"]
    assert paper["equity"] is None
    assert paper["unrealized_pnl"] is None
    assert paper["current_drawdown_pct"] is None
    assert paper["valuation_status"] == "INCOMPLETE"
    assert paper["unmarked_positions"] == 1
    assert paper["available"] is False
    # The measured part is still visible, clearly labelled as a floor.
    assert paper["known_equity"] == pytest.approx(1000.0)
    assert paper["known_unrealized_pnl"] == pytest.approx(0.0)


def test_overview_reports_a_marked_open_position(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=10.0, entry=2.0, fees=0.5)
    _snapshot(db, pair, price=3.0)

    r = client.get("/api/v1/portfolio/overview")
    paper = r.json()["modes"]["PAPER"]
    assert paper["valuation_status"] == "COMPLETE"
    assert paper["unrealized_pnl"] == pytest.approx(9.5)
    assert paper["equity"] == pytest.approx(1009.5)
    assert paper["available"] is True


def test_positions_endpoint_exposes_the_mark(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=10.0, entry=2.0, fees=0.5)
    _snapshot(db, pair, price=3.0)
    client.get("/api/v1/portfolio/overview")  # triggers the valuation pass

    r = client.get("/api/v1/portfolio/positions")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["mark_price"] == 3.0
    assert item["unrealized_pnl"] == pytest.approx(9.5)
    assert item["valuation_status"] == "KNOWN"
    assert item["valuation_as_of"] is not None


def test_positions_endpoint_reports_null_for_an_unmarked_position(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token)

    r = client.get("/api/v1/portfolio/positions")
    item = r.json()["items"][0]
    assert item["unrealized_pnl"] is None
    assert item["valuation_status"] == "UNKNOWN"
    assert item["valuation_reason"] == "no_snapshot_for_pair"


def test_accounting_audit_does_not_claim_consistency_it_cannot_prove(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token)  # unvalued

    r = client.get("/api/v1/portfolio/accounting-audit")
    body = r.json()
    assert body["consistent"] is None
    assert body["equity"] is None
    assert body["valuation_status"] == "INCOMPLETE"
    assert "unknown, not zero" in body["reason"]


def test_accounting_audit_is_consistent_for_a_marked_book(client, db):
    token, pair = _token_and_pair(db)
    _position(db, token, quantity=10.0, entry=2.0, fees=0.0)
    _snapshot(db, pair, price=3.0)

    body = client.get("/api/v1/portfolio/accounting-audit").json()
    assert body["consistent"] is True
    assert body["equity"] == pytest.approx(1010.0)


def test_equity_curve_reports_null_on_an_unvalued_book(client, db):
    from app.accounting.equity import record_event

    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=50.0, idempotency_key="x")
    token, pair = _token_and_pair(db)
    _position(db, token)  # unvalued

    body = client.get("/api/v1/portfolio/equity-curve").json()
    curve = body["curve"]
    assert curve[-1]["valuation_status"] == "INCOMPLETE"
    assert curve[-1]["equity"] is None
    # The ledger path is still reconstructable for every historical point.
    assert curve[0]["realized_equity"] == 1000.0
    assert curve[1]["realized_equity"] == pytest.approx(1050.0)
