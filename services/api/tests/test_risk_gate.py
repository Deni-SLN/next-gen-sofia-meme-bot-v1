"""Risk gate (FR-TB-004) fail-closed tests.

The gate is the last safety checkpoint before execution. NaN / Infinity /
missing mandatory metric / stale data must always reject, and there is no
AI override for hard-reject.
"""

from datetime import UTC, datetime, timedelta

from app.risk.gate import RiskGateInput, evaluate_risk_gate

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _healthy_input(**overrides):
    data = RiskGateInput(
        mode="PAPER",
        bot_running=True,
        kill_switch_active=False,
        equity_usd=1000.0,
        open_positions_count=0,
        open_exposure_usd=0.0,
        daily_realized_pnl_usd=0.0,
        peak_equity_usd=1000.0,
        last_loss_at=None,
        now=NOW,
        signal_created_at=NOW - timedelta(seconds=30),
        signal_expires_at=NOW + timedelta(seconds=600),
        reference_price=1.5,
        liquidity_usd=500000.0,
        slippage_pct=0.5,
        fee_pct=0.3,
        price_impact_pct=0.2,
        risk_reward=2.0,
        hard_reject=False,
        market_data_age_seconds=30,
    )
    for k, v in overrides.items():
        setattr(data, k, v)
    return data


def test_approves_healthy_input():
    decision = evaluate_risk_gate(_healthy_input())
    assert decision.approved
    assert decision.sized_allocation_usd is not None
    assert decision.sized_allocation_usd > 0


def test_rejects_when_kill_switch_active():
    decision = evaluate_risk_gate(_healthy_input(kill_switch_active=True))
    assert not decision.approved
    assert not decision.checks["kill_switch"]


def test_rejects_when_bot_not_running():
    decision = evaluate_risk_gate(_healthy_input(bot_running=False))
    assert not decision.approved


def test_rejects_invalid_mode():
    decision = evaluate_risk_gate(_healthy_input(mode="LIVE"))
    assert not decision.approved
    assert not decision.checks["valid_mode"]


def test_hard_reject_cannot_be_overridden():
    decision = evaluate_risk_gate(_healthy_input(hard_reject=True))
    assert not decision.approved
    assert not decision.checks["hard_reject"]


def test_nan_price_fails_closed():
    decision = evaluate_risk_gate(_healthy_input(reference_price=float("nan")))
    assert not decision.approved
    assert decision.checks["finite_reference_price"] is False


def test_infinity_liquidity_fails_closed():
    decision = evaluate_risk_gate(_healthy_input(liquidity_usd=float("inf")))
    assert not decision.approved
    assert decision.checks["finite_liquidity"] is False


def test_none_mandatory_metric_fails_closed():
    decision = evaluate_risk_gate(_healthy_input(liquidity_usd=None))
    assert not decision.approved


def test_stale_data_fails_closed():
    decision = evaluate_risk_gate(_healthy_input(market_data_age_seconds=10_000))
    assert not decision.approved
    assert decision.checks["data_fresh"] is False


def test_unknown_data_age_fails_closed():
    decision = evaluate_risk_gate(_healthy_input(market_data_age_seconds=None))
    assert not decision.approved


def test_slippage_ceiling():
    decision = evaluate_risk_gate(_healthy_input(slippage_pct=5.0))
    assert not decision.approved


def test_low_liquidity_rejected():
    decision = evaluate_risk_gate(_healthy_input(liquidity_usd=1000.0))
    assert not decision.approved


def test_low_risk_reward_rejected():
    decision = evaluate_risk_gate(_healthy_input(risk_reward=1.0))
    assert not decision.approved


def test_max_concurrent_positions():
    decision = evaluate_risk_gate(_healthy_input(open_positions_count=5))
    assert not decision.approved


def test_daily_loss_limit():
    decision = evaluate_risk_gate(_healthy_input(daily_realized_pnl_usd=-150.0))
    assert not decision.approved


def test_expired_signal_rejected():
    decision = evaluate_risk_gate(
        _healthy_input(signal_expires_at=NOW - timedelta(seconds=1))
    )
    assert not decision.approved


def test_cooldown_after_loss():
    decision = evaluate_risk_gate(
        _healthy_input(last_loss_at=NOW - timedelta(seconds=10))
    )
    assert not decision.approved
    assert decision.checks["cooldown"] is False


def test_sizing_capped_by_position_pct():
    decision = evaluate_risk_gate(_healthy_input(equity_usd=100_000.0))
    assert decision.approved
    # max_position_pct_of_equity=10% => 10k but max_position_allocation=200 => 200
    assert decision.sized_allocation_usd == 200.0


# --------------------------- drawdown must fail closed ---------------------------
#
# Regression: an unknown or non-positive peak used to skip the drawdown check
# entirely and report PASS. Unknown equity has to reject, not wave a new order
# through on the strength of a number nobody computed.


def test_drawdown_rejects_when_equity_is_unknown():
    decision = evaluate_risk_gate(_healthy_input(equity_usd=None))
    assert not decision.approved
    assert decision.checks["drawdown"] is False
    assert any("equity or peak equity unknown" in r for r in decision.reasons)


def test_drawdown_rejects_when_peak_is_unknown():
    decision = evaluate_risk_gate(_healthy_input(peak_equity_usd=None))
    assert not decision.approved
    assert decision.checks["drawdown"] is False


def test_drawdown_rejects_nan_equity():
    decision = evaluate_risk_gate(_healthy_input(equity_usd=float("nan")))
    assert not decision.approved
    assert decision.checks["drawdown"] is False
    assert decision.checks["finite_equity"] is False


def test_drawdown_rejects_infinite_equity():
    decision = evaluate_risk_gate(_healthy_input(equity_usd=float("inf")))
    assert not decision.approved
    assert decision.checks["drawdown"] is False


def test_drawdown_rejects_a_non_positive_peak():
    """A wiped-out account has no buffer; it must not read as zero drawdown."""
    decision = evaluate_risk_gate(_healthy_input(equity_usd=0.0, peak_equity_usd=0.0))
    assert not decision.approved
    assert decision.checks["drawdown"] is False
    assert any("not positive" in r for r in decision.reasons)


def test_drawdown_blocks_when_open_positions_are_unvalued():
    """Unmarkable open positions make equity unknown -> no new risk is added."""
    decision = evaluate_risk_gate(_healthy_input(valuation_complete=False))
    assert not decision.approved
    assert decision.checks["valuation_complete"] is False
    assert any("valuation incomplete" in r for r in decision.reasons)


def test_valuation_complete_defaults_true_for_a_flat_book():
    """An account with no open positions has nothing to value."""
    decision = evaluate_risk_gate(_healthy_input())
    assert decision.approved
    assert decision.checks["valuation_complete"] is True
