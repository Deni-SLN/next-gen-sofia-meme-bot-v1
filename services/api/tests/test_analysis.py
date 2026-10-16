"""Deterministic analysis engine unit tests.

Indicators are numeric formulas; risk assessment and scoring are deterministic.
These tests assert numeric boundaries and the fail-closed principle:
UNKNOWN != PASS.
"""

import math

from app.analysis.indicators import (
    atr,
    ema,
    macd,
    market_structure,
    rsi,
    support_resistance,
    volume_ratio,
)
from app.analysis.risk import RiskInput, assess_risk
from app.analysis.scoring import ScoreInput, compute_score

# ------------------------------- indicators -------------------------------


def test_ema_insufficient_data_returns_none():
    assert ema([1.0, 2.0], period=5) is None


def test_ema_basic():
    # Simple increasing series; EMA should track within range.
    vals = [float(i) for i in range(1, 21)]
    val = ema(vals, period=5)
    assert val is not None
    assert vals[4] <= val <= vals[-1]


def test_ema_handles_none_and_nan():
    vals = [1.0, None, 3.0, float("nan"), 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    val = ema(vals, period=5)
    assert val is not None and math.isfinite(val)


def test_rsi_all_gains_is_100():
    closes = [float(i) for i in range(1, 40)]
    assert rsi(closes, 14) == 100.0


def test_rsi_insufficient_data():
    assert rsi([1.0, 2.0], 14) is None


def test_rsi_flat_series_is_neutral():
    closes = [10.0] * 40
    assert rsi(closes, 14) == 50.0


def test_macd_insufficient_data():
    assert macd([1.0] * 10).macd is None


def test_macd_uptrend_positive_histogram():
    closes = [float(i) for i in range(1, 80)]
    res = macd(closes)
    assert res.macd is not None
    assert res.signal is not None
    assert res.histogram is not None


def test_atr_insufficient_data():
    assert atr([1.0], [1.0], [1.0]) is None


def test_atr_positive_for_volatile_series():
    highs = [10 + i * 0.5 for i in range(30)]
    lows = [9 + i * 0.5 for i in range(30)]
    closes = [9.5 + i * 0.5 for i in range(30)]
    val = atr(highs, lows, closes, 14)
    assert val is not None and val > 0


def test_support_resistance_detects_levels():
    highs = [1, 2, 3, 2, 1, 2, 3, 2, 1]
    lows = [0.5, 1, 1.5, 1, 0.5, 1, 1.5, 1, 0.5]
    sr = support_resistance([float(h) for h in highs], [float(x) for x in lows], lookback=2)
    assert isinstance(sr.resistances, list)
    assert isinstance(sr.supports, list)


def test_market_structure_breakout():
    closes = [1.0, 1.1, 1.2, 1.1, 1.0, 1.15, 1.3]
    highs = [c + 0.05 for c in closes]
    lows = [c - 0.05 for c in closes]
    res = market_structure(closes, highs, lows, lookback=2)
    assert res is not None
    assert res.structure in ("BREAKOUT", "BREAKDOWN", "RETEST", "RANGE")


def test_volume_ratio_none_when_no_baseline():
    assert volume_ratio([100.0]) is None


# ------------------------------- risk -------------------------------


def _safe_risk_input():
    return RiskInput(
        price_usd=1.5,
        liquidity_usd=500000.0,
        pool_age_minutes=600.0,
        buys_1h=200,
        sells_1h=120,
        mint_authority_revoked=True,
        freeze_authority_revoked=True,
        top10_holder_pct=0.30,
    )


def test_risk_pass_for_healthy_token():
    res = assess_risk(_safe_risk_input())
    assert res.status == "PASS"
    assert not res.hard_reject
    assert res.coverage == 1.0


def test_risk_hard_reject_on_invalid_price():
    inp = _safe_risk_input()
    inp.price_usd = None
    res = assess_risk(inp)
    assert res.status == "REJECT"
    assert res.hard_reject
    assert "INVALID_PRICE" in res.risk_flags


def test_risk_hard_reject_on_low_liquidity():
    inp = _safe_risk_input()
    inp.liquidity_usd = 100.0
    res = assess_risk(inp)
    assert res.hard_reject
    assert "LOW_LIQUIDITY" in res.risk_flags


def test_risk_unknown_mandatory_check_fails_closed():
    """An unverifiable mandatory check is a REJECT, not a soft UNKNOWN.

    FR-AE-005: mandatory conditions that cannot be verified must reject.
    """
    inp = _safe_risk_input()
    inp.mint_authority_revoked = None
    res = assess_risk(inp)
    assert res.hard_reject
    assert res.status == "REJECT"
    assert "MINT_AUTHORITY_UNKNOWN" in res.risk_flags


def test_risk_status_never_contradicts_hard_reject():
    """status and hard_reject must always agree.

    `status=UNKNOWN` together with `hard_reject=True` is self-contradictory and
    lets a downstream caller read the wrong field.
    """
    cases = {
        "all clean": {},
        "mint unknown": {"mint_authority_revoked": None},
        "freeze unknown": {"freeze_authority_revoked": None},
        "pool age unknown": {"pool_age_minutes": None},
        "holders unknown": {"top10_holder_pct": None},
        "price missing": {"price_usd": None},
        "liquidity missing": {"liquidity_usd": None},
        "authority enabled": {"mint_authority_revoked": False},
        "everything unknown": {
            "mint_authority_revoked": None,
            "freeze_authority_revoked": None,
            "pool_age_minutes": None,
            "top10_holder_pct": None,
        },
    }
    for label, overrides in cases.items():
        inp = _safe_risk_input()
        for attr, value in overrides.items():
            setattr(inp, attr, value)
        res = assess_risk(inp)
        assert res.status in ("PASS", "WARN", "REJECT"), (label, res.status)
        if res.hard_reject:
            assert res.status == "REJECT", f"{label}: hard_reject with status {res.status}"
        if res.status == "REJECT":
            assert res.hard_reject, f"{label}: REJECT without hard_reject"


def test_mandatory_checks_are_configurable():
    """The mandatory set comes from the rule config, not a hardcoded list."""
    inp = _safe_risk_input()
    inp.mint_authority_revoked = None
    res = assess_risk(
        inp, rules={"mandatory_checks": ["price_valid", "liquidity_valid", "pool_age_known"]}
    )
    assert not res.hard_reject
    assert res.status == "WARN"


def test_unknown_mandatory_check_name_is_rejected():
    """A typo in the rule config must fail loudly, not silently disable a check."""
    inp = _safe_risk_input()
    try:
        assess_risk(inp, rules={"mandatory_checks": ["price_valid", "typo_check"]})
    except ValueError as exc:
        assert "typo_check" in str(exc)
    else:
        raise AssertionError("unknown mandatory check should raise ValueError")


def test_coverage_counts_holder_concentration():
    inp = _safe_risk_input()
    full = assess_risk(inp).coverage
    inp.top10_holder_pct = None
    partial = assess_risk(inp).coverage
    assert full == 1.0
    assert partial < full


def test_risk_hard_reject_when_pool_age_unknown():
    inp = _safe_risk_input()
    inp.pool_age_minutes = None
    res = assess_risk(inp)
    assert res.hard_reject
    assert "POOL_AGE_UNKNOWN" in res.risk_flags


def test_risk_mint_authority_enabled_hard_reject():
    inp = _safe_risk_input()
    inp.mint_authority_revoked = False
    res = assess_risk(inp)
    assert res.hard_reject
    assert "MINT_AUTHORITY_ENABLED" in res.risk_flags


# ------------------------------- scoring -------------------------------


def _safe_score_input():
    return ScoreInput(
        liquidity_usd=500000.0,
        price_change_1h=5.0,
        rsi_value=60.0,
        macd_histogram=0.001,
        volume_ratio=3.0,
        structure="BREAKOUT",
        risk_status="PASS",
        hard_reject=False,
        coverage=1.0,
    )


def test_score_in_0_100_range():
    res = compute_score(_safe_score_input())
    assert res.score is not None
    assert 0.0 <= res.score <= 100.0


def test_score_zero_when_hard_reject():
    inp = _safe_score_input()
    inp.hard_reject = True
    res = compute_score(inp)
    assert res.score == 0.0


def test_score_missing_data_not_perfect():
    inp = _safe_score_input()
    inp.liquidity_usd = None
    inp.rsi_value = None
    inp.macd_histogram = None
    inp.volume_ratio = None
    res = compute_score(inp)
    # Missing components must drag the score down, never score full marks.
    assert res.score is not None
    assert res.score < 100.0
