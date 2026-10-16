"""Canonical equity model + paper execution tests (§11.2, FR-TB-005).

equity = initial_capital + realized_pnl + unrealized_pnl - external_cash_movements

External cash movement convention: WITHDRAWAL stored positive (leaves ledger),
DEPOSIT stored negative (enters ledger).
"""

import math

from app.accounting.equity import compute_equity, record_event, summarize_mode
from app.execution.paper import simulate_buy, simulate_sell

# --------------------------- canonical equity ---------------------------


def test_compute_equity_formula():
    equity = compute_equity(
        initial_capital=1000.0,
        realized_pnl=100.0,
        unrealized_pnl=50.0,
        external_cash_movements=0.0,
    )
    assert equity == 1150.0


def test_compute_equity_subtracts_withdrawal():
    # withdrawal stored positive => equity reduced
    equity = compute_equity(1000.0, 0.0, 0.0, external_cash_movements=200.0)
    assert equity == 800.0


def test_compute_equity_adds_deposit():
    # deposit stored negative => subtracting a negative adds it back
    equity = compute_equity(1000.0, 0.0, 0.0, external_cash_movements=-200.0)
    assert equity == 1200.0


def test_compute_equity_rejects_non_finite():
    for bad in (float("nan"), float("inf")):
        try:
            compute_equity(1000.0, bad, 0.0, 0.0)
        except ValueError:
            continue
        raise AssertionError("expected ValueError for non-finite input")


# --------------------------- paper execution ---------------------------


def test_simulate_buy_applies_slippage_and_fee():
    fill = simulate_buy(allocation_usd=100.0, reference_price=10.0, slippage_pct=1.0, fee_pct=1.0)
    assert not fill.rejected
    assert fill.fill_type == "SIMULATED"
    assert fill.price == 10.1  # slippage worsens entry
    # spend_after_fee = 100 * 0.99 = 99 ; qty = 99 / 10.1
    assert math.isclose(fill.quantity, 99.0 / 10.1, rel_tol=1e-6)
    assert math.isclose(fill.fee_amount, 1.0, rel_tol=1e-6)


def test_simulate_sell_applies_slippage_and_fee():
    fill = simulate_sell(quantity=10.0, reference_price=10.0, slippage_pct=1.0, fee_pct=1.0)
    assert not fill.rejected
    assert fill.price == 9.9  # slippage worsens exit
    notional = 10.0 * 9.9
    assert math.isclose(fill.fee_amount, notional * 0.01, rel_tol=1e-6)


def test_simulate_buy_rejects_invalid():
    fill = simulate_buy(allocation_usd=0.0, reference_price=10.0, slippage_pct=1.0, fee_pct=1.0)
    assert fill.rejected


def test_record_event_idempotent(db):
    ev1 = record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=25.0, idempotency_key="k1")
    db.commit()
    ev2 = record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=25.0, idempotency_key="k1")
    db.commit()
    assert ev1 is not None
    assert ev2 is None  # duplicate suppressed


def test_summarize_mode_equity(db):
    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=100.0, idempotency_key="p1")
    db.commit()
    snap = summarize_mode(db, "PAPER", 1000.0)
    assert snap.realized_pnl == 100.0
    assert snap.equity == 1100.0
