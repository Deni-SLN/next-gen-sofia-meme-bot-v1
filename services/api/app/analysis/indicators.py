"""Deterministic technical indicators.

All functions are pure, handle null/NaN/Infinity and insufficient data
explicitly (returning None), and never interpolate misleadingly.
"""

import math
from dataclasses import dataclass


def _finite(x: float | None) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def ema(values: list[float | None], period: int) -> float | None:
    """Exponential moving average over the tail of `values`."""
    clean = [v for v in values if _finite(v)]
    if len(clean) < period or period <= 0:
        return None
    k = 2.0 / (period + 1)
    result = sum(clean[:period]) / period
    for price in clean[period:]:
        result = price * k + result * (1 - k)
    return result


def ema_series(values: list[float | None], period: int) -> list[float | None]:
    clean = [v if _finite(v) else None for v in values]
    out: list[float | None] = [None] * len(values)
    seed = [v for v in clean[:period] if v is not None]
    if len(seed) < period:
        return out
    result = sum(seed) / period
    out[period - 1] = result
    k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        v = clean[i]
        if v is None:
            out[i] = result
            continue
        result = v * k + result * (1 - k)
        out[i] = result
    return out


def rsi(closes: list[float | None], period: int = 14) -> float | None:
    """Wilder's RSI."""
    clean = [c for c in closes if _finite(c)]
    if len(clean) < period + 1 or period <= 0:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        delta = clean[i] - clean[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(clean)):
        delta = clean[i] - clean[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


@dataclass
class MACDResult:
    macd: float | None
    signal: float | None
    histogram: float | None


def macd(
    closes: list[float | None], fast: int = 12, slow: int = 26, signal_period: int = 9
) -> MACDResult:
    if len([c for c in closes if _finite(c)]) < slow + signal_period:
        return MACDResult(None, None, None)
    fast_series = ema_series(closes, fast)
    slow_series = ema_series(closes, slow)
    # ema_series always returns one entry per input, so the lengths must match;
    # strict=True turns a future regression into an immediate error.
    macd_line = [
        (f - s) if _finite(f) and _finite(s) else None
        for f, s in zip(fast_series, slow_series, strict=True)
    ]
    valid_tail = [m for m in macd_line if _finite(m)]
    if len(valid_tail) < signal_period:
        return MACDResult(None, None, None)
    signal_line = ema(valid_tail, signal_period)
    last = valid_tail[-1]
    hist = (last - signal_line) if _finite(signal_line) else None
    return MACDResult(last, signal_line, hist)


def atr(
    highs: list[float | None],
    lows: list[float | None],
    closes: list[float | None],
    period: int = 14,
) -> float | None:
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n:
        return None
    trs: list[float] = []
    for i in range(1, n):
        high, low, prev_c = highs[i], lows[i], closes[i - 1]
        if not (_finite(high) and _finite(low) and _finite(prev_c)):
            continue
        trs.append(max(high - low, abs(high - prev_c), abs(low - prev_c)))
    if len(trs) < period:
        return None
    result = sum(trs[:period]) / period
    for tr in trs[period:]:
        result = (result * (period - 1) + tr) / period
    return result


def volume_ratio(volumes: list[float | None], baseline_period: int = 20) -> float | None:
    """Current volume vs baseline mean."""
    clean = [v for v in volumes if _finite(v)]
    if len(clean) < baseline_period + 1 or baseline_period <= 0:
        return None
    baseline_vals = clean[-(baseline_period + 1) : -1]
    baseline = sum(baseline_vals) / len(baseline_vals)
    if baseline <= 0:
        return None
    return clean[-1] / baseline


@dataclass
class SwingPoints:
    swing_highs: list[int]
    swing_lows: list[int]


def swings(highs: list[float | None], lows: list[float | None], lookback: int = 2) -> SwingPoints:
    sh: list[int] = []
    sl: list[int] = []
    n = len(highs)
    if n < lookback * 2 + 1 or len(lows) != n:
        return SwingPoints(sh, sl)
    for i in range(lookback, n - lookback):
        window_h = highs[i - lookback : i + lookback + 1]
        window_l = lows[i - lookback : i + lookback + 1]
        if not all(_finite(v) for v in window_h + window_l):
            continue
        if highs[i] == max(window_h):
            sh.append(i)
        if lows[i] == min(window_l):
            sl.append(i)
    return SwingPoints(sh, sl)


@dataclass
class SupportResistance:
    supports: list[float]
    resistances: list[float]


def support_resistance(
    highs: list[float | None], lows: list[float | None], lookback: int = 2, tolerance: float = 0.01
) -> SupportResistance:
    sw = swings(highs, lows, lookback)
    res: list[float] = []
    sup: list[float] = []
    for i in sw.swing_highs:
        h = highs[i]
        if _finite(h) and not any(abs(h - r) / r < tolerance for r in res if r > 0):
            res.append(h)
    for i in sw.swing_lows:
        low = lows[i]
        if _finite(low) and not any(abs(low - s) / s < tolerance for s in sup if s > 0):
            sup.append(low)
    return SupportResistance(supports=sorted(sup), resistances=sorted(res))


@dataclass
class StructureResult:
    structure: str  # BREAKOUT | BREAKDOWN | RETEST | RANGE
    detail: str


def market_structure(
    closes: list[float | None],
    highs: list[float | None],
    lows: list[float | None],
    lookback: int = 2,
) -> StructureResult | None:
    n = len(closes)
    if n < lookback * 2 + 2:
        return None
    last_close = closes[-1]
    if not _finite(last_close):
        return None
    sr = support_resistance(highs, lows, lookback)
    if not sr.resistances and not sr.supports:
        return StructureResult("RANGE", "no swing points identified")
    nearest_res = min((r for r in sr.resistances if r > 0), default=None)
    nearest_sup = max((s for s in sr.supports if s > 0), default=None)
    if nearest_res is not None and last_close > nearest_res:
        return StructureResult("BREAKOUT", f"close {last_close} above resistance {nearest_res}")
    if nearest_sup is not None and last_close < nearest_sup:
        return StructureResult("BREAKDOWN", f"close {last_close} below support {nearest_sup}")
    if (
        nearest_res is not None
        and nearest_sup is not None
        and nearest_res > nearest_sup
        and (nearest_res - nearest_sup) / nearest_sup < 0.06
    ):
        return StructureResult("RETEST", f"close within tight range {nearest_sup}-{nearest_res}")
    return StructureResult("RANGE", "no dominant structure")


def estimate_price_impact(trade_usd: float, liquidity_usd: float | None) -> float | None:
    """Rough constant-product price impact estimate."""
    if not _finite(trade_usd) or trade_usd < 0 or not _finite(liquidity_usd) or liquidity_usd <= 0:
        return None
    return trade_usd / (liquidity_usd + trade_usd)


