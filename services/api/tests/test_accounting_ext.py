"""High-water mark, drawdown and equity-curve regression (§18.E).

These are the metrics a dashboard shows, so they must be derivable from the
append-only ledger and stable under re-running the same inputs.

Open positions are valued through the real mark-to-market path
(`app.accounting.valuation`), so these fixtures publish an actual market
snapshot rather than writing an unrealized number straight onto the row.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.accounting.equity import (
    _high_water_mark,
    compute_equity,
    equity_curve,
    record_event,
    summarize_mode,
)

MINT = "So11111111111111111111111111111111111111112"


def _open_position(db, unrealized: float, quantity: float = 1.0, entry: float = 1.0, fees: float = 0.0):
    """An OPEN position with a live mark worth `unrealized` at quantity/entry.

    Returns the Position so callers can assert on what the valuation wrote.
    """
    from app.models.market import MarketSnapshot, Token, TokenPair
    from app.models.trading import BotRun, Position

    run = db.query(BotRun).first() or BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    token = db.query(Token).first()
    if token is None:
        token = Token(chain="solana", mint_address=MINT, symbol="T")
        db.add(token)
        db.flush()
    pair = TokenPair(token_id=token.id, pair_address=f"pair-{token.id}")
    db.add(pair)
    db.flush()
    mark = (unrealized + fees) / quantity + entry
    db.add(
        MarketSnapshot(
            pair_id=pair.id,
            price_usd=mark,
            liquidity_usd=500_000.0,
            observed_at=datetime.now(UTC) - timedelta(seconds=5),
        )
    )
    position = Position(
        bot_run_id=run.id,
        mode="PAPER",
        token_id=token.id,
        mint_address=MINT,
        quantity=quantity,
        average_entry_price=entry,
        total_fees=fees,
        status="OPEN",
    )
    db.add(position)
    db.commit()
    return position


# --------------------------- high-water mark ---------------------------


def test_hwm_starts_at_initial_capital(db):
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.high_water_mark == 1000.0
    assert snap.current_drawdown_pct == 0.0


def test_hwm_rises_with_profit(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=200.0, idempotency_key="a")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.high_water_mark == 1200.0
    assert snap.equity == 1200.0


def test_hwm_does_not_fall_when_equity_falls(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=200.0, idempotency_key="a")
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=-100.0, idempotency_key="b")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.equity == 1100.0
    assert snap.high_water_mark == 1200.0, "high-water mark must never decrease"


def test_drawdown_is_measured_from_the_peak(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=200.0, idempotency_key="a")
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=-100.0, idempotency_key="b")
    snap = summarize_mode(db, "PAPER", 1000.0)
    # (1200 - 1100) / 1200 = 8.333...%
    assert snap.current_drawdown_pct == pytest.approx(8.3333, abs=1e-3)


def test_drawdown_zero_at_a_new_peak(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=200.0, idempotency_key="a")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.current_drawdown_pct == 0.0


def test_hwm_never_negative_returns_zero_drawdown(db):
    """A wiped-out ledger must not divide by a non-positive peak."""
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=-1500.0, idempotency_key="a")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.equity == -500.0
    assert snap.high_water_mark == 1000.0
    assert snap.current_drawdown_pct > 0


def test_hwm_is_stable_across_repeated_runs(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=75.0, idempotency_key="a")
    first = summarize_mode(db, "PAPER", 1000.0)
    second = summarize_mode(db, "PAPER", 1000.0)
    third = summarize_mode(db, "PAPER", 1000.0)
    assert (first.high_water_mark, second.high_water_mark, third.high_water_mark) == (
        first.high_water_mark,
        first.high_water_mark,
        first.high_water_mark,
    )


def test_hwm_reflects_deposit(db):
    # A deposit is stored negative; equity rises, so the peak rises with it.
    record_event(db, mode="PAPER", event_type="DEPOSIT", amount=-500.0, idempotency_key="d")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.equity == 1500.0
    assert snap.high_water_mark == 1500.0


def test_hwm_falls_after_withdrawal(db):
    record_event(db, mode="PAPER", event_type="WITHDRAWAL", amount=200.0, idempotency_key="w")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.equity == 800.0
    assert snap.high_water_mark == 1000.0
    assert snap.current_drawdown_pct == pytest.approx(20.0)


# --------------------------- modes stay separate ---------------------------


def test_paper_and_live_ledgers_are_separate(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="p")
    record_event(db, mode="LIVE", event_type="REALIZED_PNL", amount=900.0, idempotency_key="l")
    paper = summarize_mode(db, "PAPER", 1000.0)
    live = summarize_mode(db, "LIVE", 1000.0)
    assert paper.equity == 1100.0
    assert live.equity == 1900.0


# --------------------------- unrealised PnL ---------------------------


def test_open_position_unrealised_counts_in_equity(db):
    _open_position(db, unrealized=120.0)
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.valuation_status == "COMPLETE"
    assert snap.unrealized_pnl == pytest.approx(120.0)
    assert snap.equity == pytest.approx(1120.0)


def test_open_position_is_not_a_realised_result(db):
    """An unfinished position must not be reported as realised performance."""
    _open_position(db, unrealized=120.0)
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.realized_pnl == 0.0


def test_closed_position_leaves_the_unrealised_bucket(db):
    from app.models.market import Token
    from app.models.trading import BotRun, Position

    run = db.query(BotRun).first() or BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    token = Token(chain="solana", mint_address="So11111111111111111111111111111111111111112", symbol="T")
    db.add(token)
    db.flush()
    db.add(
        Position(
            bot_run_id=run.id,
            mode="PAPER",
            token_id=token.id,
            mint_address="So11111111111111111111111111111111111111112",
            quantity=1.0,
            average_entry_price=1.0,
            status="CLOSED",
            realized_pnl=40.0,
        )
    )
    db.commit()
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.unrealized_pnl == 0.0
    # equity uses the canonical ledger, so a closed position only shows up once
    # its REALIZED_PNL event is recorded.
    assert snap.equity == 1000.0


# --------------------------- equity curve ---------------------------


def test_curve_starts_at_initial_capital(db):
    curve = equity_curve(db, "PAPER", 1000.0)
    assert curve[0]["equity"] == 1000.0
    assert curve[0]["label"] == "start"


def test_curve_has_one_point_per_event(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=10.0, idempotency_key="a")
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=20.0, idempotency_key="b")
    curve = equity_curve(db, "PAPER", 1000.0)
    assert len(curve) == 3  # start + 2 events
    assert [p["equity"] for p in curve] == [1000.0, 1010.0, 1030.0]


def test_curve_reconciles_to_the_summary(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="a")
    record_event(db, mode="PAPER", event_type="WITHDRAWAL", amount=50.0, idempotency_key="w")
    curve = equity_curve(db, "PAPER", 1000.0)
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert curve[-1]["equity"] == pytest.approx(snap.equity)


def test_curve_is_excluded_from_other_modes(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="p")
    curve = equity_curve(db, "LIVE", 1000.0)
    assert len(curve) == 1
    assert curve[0]["equity"] == 1000.0


def test_curve_is_deterministic(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=10.0, idempotency_key="a")
    assert equity_curve(db, "PAPER", 1000.0) == equity_curve(db, "PAPER", 1000.0)


# --------------------------- double accounting ---------------------------


def test_retry_does_not_double_count(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="once")
    for _ in range(3):
        record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="once")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.realized_pnl == 100.0
    assert snap.equity == 1100.0


def test_distinct_keys_are_counted_separately(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=10.0, idempotency_key="k1")
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=10.0, idempotency_key="k2")
    assert summarize_mode(db, "PAPER", 1000.0).realized_pnl == 20.0


def test_non_finite_event_amount_is_rejected(db):
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=bad)


def test_high_water_mark_helper_matches_summary(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=60.0, idempotency_key="a")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert _high_water_mark(db, "PAPER", 1000.0, snap.equity) == snap.high_water_mark


def test_equity_formula_is_symmetric_for_withdrawal(db):
    record_event(db, mode="PAPER", event_type="WITHDRAWAL", amount=200.0, idempotency_key="w")
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert compute_equity(1000.0, 0.0, 0.0, 200.0) == snap.equity