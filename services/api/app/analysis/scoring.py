"""Weighted scoring 0-100 (FR-AE-006). Relative summary, NOT profit probability.

Rules: weights sum to 100%; missing data never scores full marks;
coverage/confidence kept separate; hard-reject beats any score.
"""

import math
from dataclasses import dataclass, field

DEFAULT_WEIGHTS: dict[str, float] = {
    "liquidity_quality": 25.0,
    "trend_momentum": 25.0,
    "volume_activity": 15.0,
    "price_structure": 15.0,
    "onchain_risk": 20.0,
}
SCORING_CONFIG_VERSION = "scoring-v1"

# Weight keys must always be a fixed set so a persisted config cannot silently
# drop or invent a component.
WEIGHT_KEYS = tuple(DEFAULT_WEIGHTS)


@dataclass
class ScoreInput:
    liquidity_usd: float | None
    price_change_1h: float | None
    rsi_value: float | None
    macd_histogram: float | None
    volume_ratio: float | None
    structure: str | None  # BREAKOUT|BREAKDOWN|RETEST|RANGE
    risk_status: str  # PASS|WARN|REJECT|UNKNOWN
    hard_reject: bool
    coverage: float


@dataclass
class ScoreResult:
    score: float | None
    # Coverage is reported next to the score but never folded into it: a token
    # scored on thin evidence must not look as trustworthy as a fully covered
    # one (FR-AE-006).
    coverage: float = 0.0
    components: dict[str, float | None] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    config_version: str = SCORING_CONFIG_VERSION
    notes: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def normalize_weights(weights: dict[str, float] | None) -> tuple[dict[str, float], list[str]]:
    """Merge a partial override onto the defaults and force the sum to 100%.

    Unknown keys are rejected so a typo in a stored config cannot quietly
    remove a component (and its weight) from the score.
    """
    notes: list[str] = []
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        unknown = sorted(set(weights) - set(DEFAULT_WEIGHTS))
        if unknown:
            raise ValueError(f"unknown scoring weights: {unknown}")
        for key, value in weights.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"weight {key!r} must be a number")
            if value < 0:
                raise ValueError(f"weight {key!r} must not be negative")
            if not math.isfinite(value):
                raise ValueError(f"weight {key!r} must be finite")
            w[key] = float(value)
    total = sum(w.values())
    if abs(total - 100.0) > 1e-6:
        notes.append(f"weights sum {round(total, 6)} != 100, normalizing")
        w = {k: v * 100.0 / total for k, v in w.items()}
    return w, notes


def compute_score(data: ScoreInput, weights: dict[str, float] | None = None) -> ScoreResult:
    w, notes = normalize_weights(weights)

    components: dict[str, float | None] = {}

    # Liquidity / market quality: log scale between 5k and 5M
    if data.liquidity_usd is not None and data.liquidity_usd > 0:
        components["liquidity_quality"] = _clamp(
            (math.log10(data.liquidity_usd) - math.log10(5_000))
            / (math.log10(5_000_000) - math.log10(5_000))
            * 100
        )
    else:
        components["liquidity_quality"] = None

    # Trend / momentum: RSI + MACD histogram
    rsi_part = None
    if data.rsi_value is not None:
        r = data.rsi_value
        rsi_part = _clamp(100 - abs(r - 60) * 2.2)  # prefer ~60 momentum zone
    macd_part = None
    if data.macd_histogram is not None:
        macd_part = _clamp(50 + data.macd_histogram * 5000) if data.macd_histogram > -0.1 else 20.0
    if rsi_part is not None or macd_part is not None:
        vals = [v for v in (rsi_part, macd_part) if v is not None]
        components["trend_momentum"] = sum(vals) / len(vals)
    else:
        components["trend_momentum"] = None

    # Volume / activity
    if data.volume_ratio is not None:
        components["volume_activity"] = _clamp(data.volume_ratio * 33.0)
    else:
        components["volume_activity"] = None

    # Price structure
    structure_map = {"BREAKOUT": 85.0, "RETEST": 65.0, "RANGE": 45.0, "BREAKDOWN": 15.0}
    if data.structure in structure_map:
        chg = data.price_change_1h
        bonus = _clamp(chg * 1.5, -15, 15) if chg is not None else 0.0
        components["price_structure"] = _clamp(structure_map[data.structure] + bonus)
    else:
        components["price_structure"] = None

    # On-chain risk (inverted: lower risk = higher subscore)
    onchain_map = {"PASS": 90.0, "WARN": 55.0, "UNKNOWN": 25.0, "REJECT": 0.0}
    components["onchain_risk"] = onchain_map.get(data.risk_status, 25.0)

    known = {k: v for k, v in components.items() if v is not None}
    missing = [k for k, v in components.items() if v is None]
    if missing:
        notes.append(f"missing components treated as 0: {', '.join(missing)}")

    # Missing data must not receive a perfect score -> score missing as 0 contribution
    score = sum(known.get(k, 0.0) * w[k] / 100.0 for k in w)

    if data.hard_reject:
        notes.append("hard-reject present: score cannot be used to qualify token")
        score = 0.0

    coverage = _clamp(data.coverage if math.isfinite(data.coverage) else 0.0, 0.0, 1.0)
    return ScoreResult(
        score=round(score, 4),
        coverage=round(coverage, 4),
        components=components,
        weights=w,
        notes=notes,
    )
