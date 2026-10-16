"""Tests for the cleanup work in scoring.py, signal_gen.py and risk.py.

These cover behaviour that was previously dead, unused, or self-contradictory.
"""

import pytest
from app.analysis.risk import (
    DEFAULT_RULES,
    MANDATORY_UNKNOWN_FLAGS,
    RiskInput,
    assess_risk,
)
from app.analysis.scoring import (
    DEFAULT_WEIGHTS,
    WEIGHT_KEYS,
    ScoreInput,
    compute_score,
    normalize_weights,
)
from app.analysis.signal_gen import generate_signal_plan


def _score_input(**over):
    base = dict(
        liquidity_usd=50_000.0,
        price_change_1h=2.0,
        rsi_value=58.0,
        macd_histogram=0.01,
        volume_ratio=2.0,
        structure="BREAKOUT",
        risk_status="PASS",
        hard_reject=False,
        coverage=1.0,
    )
    base.update(over)
    return ScoreInput(**base)


def _risk_input(**over):
    base = dict(
        price_usd=1.0,
        liquidity_usd=50_000.0,
        pool_age_minutes=120.0,
        buys_1h=100,
        sells_1h=50,
        mint_authority_revoked=True,
        freeze_authority_revoked=True,
        top10_holder_pct=0.20,
    )
    base.update(over)
    return RiskInput(**base)


# ----------------------------- Scoring: coverage -----------------------------


def test_score_result_reports_coverage_separately():
    """FR-AE-006: coverage must be reported next to the score, never folded in."""
    full = compute_score(_score_input(coverage=1.0))
    thin = compute_score(_score_input(coverage=0.4))
    assert full.coverage == 1.0
    assert thin.coverage == 0.4
    # Coverage must not change the score itself.
    assert full.score == thin.score


def test_coverage_is_clamped_and_nan_safe():
    assert compute_score(_score_input(coverage=5.0)).coverage == 1.0
    assert compute_score(_score_input(coverage=-2.0)).coverage == 0.0
    assert compute_score(_score_input(coverage=float("nan"))).coverage == 0.0


# ----------------------------- Scoring: weights -----------------------------


def test_default_weights_sum_to_100():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 100.0) < 1e-9
    assert set(WEIGHT_KEYS) == set(DEFAULT_WEIGHTS)


def test_weights_are_normalized_when_they_do_not_sum_to_100():
    w, notes = normalize_weights({"liquidity_quality": 50.0})
    assert abs(sum(w.values()) - 100.0) < 1e-9
    assert any("normalizing" in n for n in notes)


def test_unknown_weight_key_is_rejected():
    """A typo must not silently drop a component from the score."""
    with pytest.raises(ValueError) as exc:
        normalize_weights({"liquidity_qualty": 25.0})
    assert "liquidity_qualty" in str(exc.value)


def test_negative_and_non_finite_weights_are_rejected():
    for bad in ({"trend_momentum": -1.0}, {"trend_momentum": float("nan")}, {"trend_momentum": float("inf")}):
        with pytest.raises(ValueError):
            normalize_weights(bad)


def test_non_numeric_weight_is_rejected():
    with pytest.raises(ValueError):
        normalize_weights({"trend_momentum": "25"})


def test_bool_weight_is_rejected():
    """True would otherwise count as 1.0 and silently skew the score."""
    with pytest.raises(ValueError):
        normalize_weights({"trend_momentum": True})


# ----------------------------- Risk: mandatory checks -----------------------------


def test_every_mandatory_check_has_a_flag_mapping():
    for check in DEFAULT_RULES["mandatory_checks"]:
        assert check in MANDATORY_UNKNOWN_FLAGS, check


def test_unknown_mandatory_check_fails_closed():
    res = assess_risk(_risk_input(mint_authority_revoked=None))
    assert res.hard_reject is True
    assert res.status == "REJECT"


def test_demoting_a_mandatory_check_downgrades_to_warn():
    res = assess_risk(
        _risk_input(mint_authority_revoked=None),
        rules={"mandatory_checks": ["price_valid", "liquidity_valid", "pool_age_known"]},
    )
    assert res.hard_reject is False
    assert res.status == "WARN"
    # The flag still records the factual state even when not fatal.
    assert "MINT_AUTHORITY_UNKNOWN" in res.risk_flags


def test_status_and_hard_reject_never_disagree():
    scenarios = [
        {},
        {"mint_authority_revoked": None},
        {"freeze_authority_revoked": None},
        {"pool_age_minutes": None},
        {"top10_holder_pct": None},
        {"price_usd": None},
        {"liquidity_usd": None},
        {"price_usd": float("nan")},
        {"liquidity_usd": float("inf")},
        {"mint_authority_revoked": False},
        {"freeze_authority_revoked": False},
        {"pool_age_minutes": 1.0},
        {"top10_holder_pct": 0.95},
    ]
    for overrides in scenarios:
        res = assess_risk(_risk_input(**overrides))
        assert res.status in ("PASS", "WARN", "REJECT")
        assert (res.status == "REJECT") == res.hard_reject, overrides


def test_unknown_check_name_raises():
    with pytest.raises(ValueError):
        assess_risk(_risk_input(), rules={"mandatory_checks": ["nope"]})


def test_coverage_reflects_every_known_input():
    assert assess_risk(_risk_input()).coverage == 1.0
    assert assess_risk(_risk_input(top10_holder_pct=None)).coverage < 1.0
    # Three of six checks unknown -> exactly half the evidence available.
    assert assess_risk(
        _risk_input(mint_authority_revoked=None, freeze_authority_revoked=None, top10_holder_pct=None)
    ).coverage == pytest.approx(0.5)


def test_evidence_refs_record_every_check():
    res = assess_risk(_risk_input())
    checks = {e["check"] for e in res.evidence_refs}
    assert {
        "price_valid",
        "liquidity_valid",
        "pool_age_known",
        "mint_authority",
        "freeze_authority",
        "holder_concentration",
        "activity",
    } <= checks


def test_nan_price_fails_closed():
    res = assess_risk(_risk_input(price_usd=float("nan")))
    assert res.hard_reject
    assert "INVALID_PRICE" in res.risk_flags


# ----------------------------- Signal: resistance -----------------------------


def _risk_pass():
    return assess_risk(_risk_input())


def _score_good():
    return compute_score(_score_input())


def test_entry_above_resistance_is_rejected():
    plan = generate_signal_plan(
        price=100.0,
        atr_value=2.0,
        support=95.0,
        resistance=98.0,  # already below entry: no room
        structure="BREAKOUT",
        risk=_risk_pass(),
        score=_score_good(),
        liquidity_usd=1_000_000.0,
    )
    assert plan.decision == "WAIT"
    assert any("resistance" in r for r in plan.reasons)


def test_nearby_resistance_caps_targets():
    plan = generate_signal_plan(
        price=100.0,
        atr_value=2.0,  # stop at 97 -> risk 3
        support=95.0,
        resistance=103.0,  # only 1R of room
        structure="BREAKOUT",
        risk=_risk_pass(),
        score=_score_good(),
        liquidity_usd=1_000_000.0,
    )
    # 1R of room < the 1.5 minimum, so the trade is not taken.
    assert plan.decision == "WAIT"
    assert any("resistance" in r for r in plan.reasons)


def test_distant_resistance_leaves_plan_untouched():
    plan = generate_signal_plan(
        price=100.0,
        atr_value=2.0,
        support=95.0,
        resistance=500.0,
        structure="BREAKOUT",
        risk=_risk_pass(),
        score=_score_good(),
        liquidity_usd=1_000_000.0,
    )
    assert plan.decision == "LONG_CANDIDATE"
    assert plan.stop_reference == pytest.approx(97.0)
    assert plan.target_references[0] == pytest.approx(106.0)
    assert plan.target_references[1] == pytest.approx(109.0)


def test_none_resistance_is_tolerated():
    plan = generate_signal_plan(
        price=100.0,
        atr_value=2.0,
        support=95.0,
        resistance=None,
        structure="BREAKOUT",
        risk=_risk_pass(),
        score=_score_good(),
        liquidity_usd=1_000_000.0,
    )
    assert plan.decision == "LONG_CANDIDATE"


def test_zero_resistance_is_tolerated():
    """A missing measurement reported as 0 must not reject every signal."""
    plan = generate_signal_plan(
        price=100.0,
        atr_value=2.0,
        support=95.0,
        resistance=0.0,
        structure="BREAKOUT",
        risk=_risk_pass(),
        score=_score_good(),
        liquidity_usd=1_000_000.0,
    )
    assert plan.decision == "LONG_CANDIDATE"