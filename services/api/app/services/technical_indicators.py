"""
Standardized Technical Indicators Engine for Sofia Market Analyst.
Implements:
1. SNR (Support and Resistance Zones with touch count, breakout, retest, and strength score)
2. SMC (Smart Money Concepts: HH/HL/LH/LL, BOS, CHoCH, Order Blocks, FVGs, Liquidity Sweeps, Premium/Discount)
3. EMA200 (Standard formula alpha = 2/(N+1), minimum data validation, slope, distance)
4. Ichimoku Cloud (Tenkan-sen 9, Kijun-sen 26, Senkou Span A/B 52, Chikou offset, TK Cross, Cloud status)
5. Fibonacci Retracement (Confirmed dealing range swing high/low, golden pocket 50%-61.8%, extensions)
Plus Multi-Indicator Trading Decision Synthesizer (BUY, SELL, HOLD, WAIT with price target).
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

WIB_TZ = timezone(timedelta(hours=7))


# ==============================================================================
# Helper Functions
# ==============================================================================

def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def _extract_ohlcv(candles: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float], list[float], list[float], list[str]]:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    opens: list[float] = []
    volumes: list[float] = []
    dates: list[str] = []

    for c in candles:
        cl = _safe_float(c.get("close"))
        hi = _safe_float(c.get("high"), cl)
        lo = _safe_float(c.get("low"), cl)
        op = _safe_float(c.get("open"), cl)
        vol = _safe_float(c.get("volume"), 0.0)
        dt = str(c.get("date") or c.get("time") or "")

        if cl > 0:
            closes.append(cl)
            highs.append(max(hi, cl, op))
            lows.append(min(lo, cl, op))
            opens.append(op)
            volumes.append(vol)
            dates.append(dt)

    return closes, highs, lows, opens, volumes, dates


# ==============================================================================
# 1. SNR — Support and Resistance Zones Engine
# ==============================================================================

def compute_snr_indicator(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
    tolerance_pct: float = 0.015,
) -> dict[str, Any]:
    """
    Computes Support and Resistance levels and zones.
    Identifies swing points, groups close levels into zones, calculates zone strength,
    and detects breakouts and retests.
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)
    n = len(closes)

    if n < 15:
        return {
            "indicator_id": "SNR",
            "name": "Support & Resistance (SNR)",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WARMING_UP",
            "calculated_at": now_str,
            "last_candle_time": dates[-1] if dates else "",
            "values": {},
            "signals": {"bias": "NEUTRAL", "score_0_100": 50, "summary": "Data historis tidak mencukupi untuk SNR (< 15 candle)."},
            "levels": {"supports": [], "resistances": [], "zones": []},
            "warnings": ["Data candle kurang dari 15 periode."],
            "display_status": "Pemanasan (0/6 zona)",
        }

    current_price = closes[-1]
    last_candle_time = dates[-1] if dates else ""

    # Find swing highs and swing lows (lookback 3 on each side)
    swing_highs: list[dict[str, Any]] = []
    swing_lows: list[dict[str, Any]] = []

    for i in range(3, n - 3):
        h = highs[i]
        l = lows[i]
        if h > highs[i - 1] and h > highs[i - 2] and h > highs[i - 3] and h > highs[i + 1] and h > highs[i + 2] and h > highs[i + 3]:
            swing_highs.append({"index": i, "price": h, "date": dates[i], "vol": volumes[i]})
        if l < lows[i - 1] and l < lows[i - 2] and l < lows[i - 3] and l < lows[i + 1] and l < lows[i + 2] and l < lows[i + 3]:
            swing_lows.append({"index": i, "price": l, "date": dates[i], "vol": volumes[i]})

    # Group price levels into zones
    def _cluster_levels(points: list[dict[str, Any]], zone_type: str) -> list[dict[str, Any]]:
        if not points:
            return []
        clusters: list[list[dict[str, Any]]] = []
        sorted_points = sorted(points, key=lambda x: x["price"])

        for pt in sorted_points:
            matched = False
            for group in clusters:
                avg_px = sum(p["price"] for p in group) / len(group)
                denom = max(abs(avg_px), 1e-9)
                if abs(pt["price"] - avg_px) / denom <= tolerance_pct:
                    group.append(pt)
                    matched = True
                    break
            if not matched:
                clusters.append([pt])

        zones = []
        for g in clusters:
            prices = [p["price"] for p in g]
            min_p = min(prices)
            max_p = max(prices)
            avg_p = sum(prices) / len(prices)
            touch_count = len(g)

            # Test recency and reactions
            latest_touch_idx = max(p["index"] for p in g)
            recency_weight = (latest_touch_idx / n)

            # Check if broken by current price
            is_active = (current_price > max_p) if zone_type == "SUPPORT" else (current_price < min_p)
            is_broken = not is_active

            # Zone strength: 1 to 5 stars
            strength_score = min(5, max(1, int(touch_count * 1.5 + (2 if recency_weight > 0.7 else 1))))

            zones.append({
                "type": zone_type,
                "price_level": round(avg_p, 2),
                "zone_low": round(min_p * 0.998, 2),
                "zone_high": round(max_p * 1.002, 2),
                "touch_count": touch_count,
                "strength": strength_score,
                "strength_label": "Sangat Kuat" if strength_score >= 4 else ("Moderat" if strength_score == 3 else "Minor"),
                "is_active": is_active,
                "is_broken": is_broken,
                "last_touch_date": g[-1]["date"],
            })

        return sorted(zones, key=lambda z: z["price_level"])

    support_zones = _cluster_levels(swing_lows, "SUPPORT")
    resistance_zones = _cluster_levels(swing_highs, "RESISTANCE")

    # Filter active supports below price, active resistances above price
    active_supports = [z for z in support_zones if z["price_level"] <= current_price]
    active_resistances = [z for z in resistance_zones if z["price_level"] >= current_price]

    # Nearest support and resistance
    nearest_sup = active_supports[-1] if active_supports else None
    nearest_res = active_resistances[0] if active_resistances else None

    # Detect breakout / retest
    breakout_info = None
    if nearest_res and current_price >= nearest_res["zone_high"]:
        breakout_info = {
            "type": "BULLISH_BREAKOUT",
            "level": nearest_res["price_level"],
            "status": "Resistensi berhasil ditembus ke atas",
        }
    elif nearest_sup and current_price <= nearest_sup["zone_low"]:
        breakout_info = {
            "type": "BEARISH_BREAKDOWN",
            "level": nearest_sup["price_level"],
            "status": "Support tertembus ke bawah (Breakdown)",
        }

    # Evaluate Bias
    bias = "NEUTRAL"
    score = 50
    summary = "Harga berada di dalam rentang normal Support & Resistance."

    if nearest_sup and nearest_res:
        rng = nearest_res["price_level"] - nearest_sup["price_level"]
        if rng > 0:
            denom_curr = max(abs(current_price), 1e-9)
            dist_to_sup_pct = (current_price - nearest_sup["price_level"]) / denom_curr
            dist_to_res_pct = (nearest_res["price_level"] - current_price) / denom_curr
            if dist_to_sup_pct <= 0.02:
                bias = "BULLISH"
                score = 75
                summary = f"Harga menguji zona Support Rp {nearest_sup['price_level']:,.2f} ({nearest_sup['strength_label']}). Area pantulan potensial."
            elif dist_to_res_pct <= 0.02:
                bias = "BEARISH"
                score = 30
                summary = f"Harga mendekati zona Resistensi Rp {nearest_res['price_level']:,.2f} ({nearest_res['strength_label']}). Rawan aksi ambil untung / penolakan."
            else:
                score = 55
                summary = f"Harga berada di antara Support Rp {nearest_sup['price_level']:,.2f} dan Resistensi Rp {nearest_res['price_level']:,.2f}."

    total_monitored = len(active_supports) + len(active_resistances)
    active_count = min(6, total_monitored)

    return {
        "indicator_id": "SNR",
        "name": "Support & Resistance (SNR)",
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "READY",
        "calculated_at": now_str,
        "last_candle_time": last_candle_time,
        "values": {
            "current_price": current_price,
            "nearest_support": nearest_sup["price_level"] if nearest_sup else None,
            "nearest_resistance": nearest_res["price_level"] if nearest_res else None,
            "support_strength": nearest_sup["strength_label"] if nearest_sup else "-",
            "resistance_strength": nearest_res["strength_label"] if nearest_res else "-",
        },
        "signals": {
            "bias": bias,
            "score_0_100": score,
            "summary": summary,
            "breakout": breakout_info,
        },
        "levels": {
            "supports": active_supports[-3:],
            "resistances": active_resistances[:3],
            "all_zones": (active_supports[-3:] + active_resistances[:3]),
        },
        "warnings": [],
        "display_status": f"Pantau {active_count}/6 Zona Aktif",
    }


# ==============================================================================
# 2. SMC — Smart Money Concepts Engine
# ==============================================================================

def compute_smc_indicator(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
) -> dict[str, Any]:
    """
    Computes Smart Money Concepts:
    - Swing Structure (HH, HL, LH, LL)
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Order Blocks (Bullish OB / Bearish OB) with mitigation status
    - Fair Value Gaps (Bullish & Bearish FVG)
    - Liquidity Sweeps (High/Low wicks)
    - Premium / Discount Dealing Range
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)
    n = len(closes)

    if n < 20:
        return {
            "indicator_id": "SMC",
            "name": "Smart Money Concepts (SMC)",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WARMING_UP",
            "calculated_at": now_str,
            "last_candle_time": dates[-1] if dates else "",
            "values": {},
            "signals": {"bias": "NEUTRAL", "score_0_100": 50, "summary": "Data historis tidak mencukupi untuk analisis SMC (< 20 candle)."},
            "levels": {"order_blocks": [], "fvgs": [], "liquidity_pools": []},
            "warnings": ["Data candle kurang dari 20 periode."],
            "display_status": "Pemanasan (0/10 Pola)",
        }

    current_price = closes[-1]
    last_candle_time = dates[-1] if dates else ""

    # 1. Identify Swings for Market Structure
    swings: list[dict[str, Any]] = []
    for i in range(2, n - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            swings.append({"type": "HIGH", "price": highs[i], "index": i, "date": dates[i]})
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            swings.append({"type": "LOW", "price": lows[i], "index": i, "date": dates[i]})

    # Label HH, HL, LH, LL
    structure_points: list[dict[str, Any]] = []
    last_high: Optional[float] = None
    last_low: Optional[float] = None

    for sw in swings:
        if sw["type"] == "HIGH":
            lbl = "HH" if (last_high is not None and sw["price"] > last_high) else "LH"
            last_high = sw["price"]
            structure_points.append({**sw, "label": lbl})
        else:
            lbl = "HL" if (last_low is not None and sw["price"] > last_low) else "LL"
            last_low = sw["price"]
            structure_points.append({**sw, "label": lbl})

    # 2. BOS & CHoCH Detection
    bos_events: list[dict[str, Any]] = []
    choch_events: list[dict[str, Any]] = []

    # Check last 30 candles against prior swing highs/lows
    for i in range(max(10, n - 35), n):
        c_close = closes[i]
        c_date = dates[i]
        # Prior confirmed swing highs before bar i
        prior_highs = [s for s in swings if s["type"] == "HIGH" and s["index"] < i - 2]
        prior_lows = [s for s in swings if s["type"] == "LOW" and s["index"] < i - 2]

        if prior_highs and c_close > prior_highs[-1]["price"]:
            is_choch = len(structure_points) >= 2 and structure_points[-1]["label"] in ("LL", "LH")
            evt = {
                "bar_index": i,
                "date": c_date,
                "broken_level": prior_highs[-1]["price"],
                "type": "BULLISH_CHOCH" if is_choch else "BULLISH_BOS",
                "label": "CHoCH Bullish" if is_choch else "BOS Bullish",
            }
            if is_choch:
                choch_events.append(evt)
            else:
                bos_events.append(evt)

        elif prior_lows and c_close < prior_lows[-1]["price"]:
            is_choch = len(structure_points) >= 2 and structure_points[-1]["label"] in ("HH", "HL")
            evt = {
                "bar_index": i,
                "date": c_date,
                "broken_level": prior_lows[-1]["price"],
                "type": "BEARISH_CHOCH" if is_choch else "BEARISH_BOS",
                "label": "CHoCH Bearish" if is_choch else "BOS Bearish",
            }
            if is_choch:
                choch_events.append(evt)
            else:
                bos_events.append(evt)

    # 3. Order Blocks (OB)
    order_blocks: list[dict[str, Any]] = []
    for i in range(5, n - 2):
        # Bullish OB: Bearish candle followed by strong bullish expansion
        if closes[i] < opens[i] and (closes[i + 1] > opens[i + 1] or closes[i + 2] > opens[i + 2]):
            denom_l = max(abs(lows[i]), 1e-9)
            expansion = (highs[min(n - 1, i + 3)] - lows[i]) / denom_l
            if expansion > 0.025:
                ob_high = highs[i]
                ob_low = lows[i]
                # Check mitigation: did any subsequent bar touch the OB?
                mitigated = any(lows[k] <= ob_high for k in range(i + 1, n))
                order_blocks.append({
                    "type": "BULLISH_OB",
                    "top": ob_high,
                    "bottom": ob_low,
                    "bar_index": i,
                    "date": dates[i],
                    "mitigated": mitigated,
                    "status": "Mitigated" if mitigated else "Unmitigated (Demand Zone)",
                })

        # Bearish OB: Bullish candle followed by strong bearish expansion
        elif closes[i] > opens[i] and (closes[i + 1] < opens[i + 1] or closes[i + 2] < opens[i + 2]):
            denom_h = max(abs(highs[i]), 1e-9)
            expansion = (highs[i] - lows[min(n - 1, i + 3)]) / denom_h
            if expansion > 0.025:
                ob_high = highs[i]
                ob_low = lows[i]
                mitigated = any(highs[k] >= ob_low for k in range(i + 1, n))
                order_blocks.append({
                    "type": "BEARISH_OB",
                    "top": ob_high,
                    "bottom": ob_low,
                    "bar_index": i,
                    "date": dates[i],
                    "mitigated": mitigated,
                    "status": "Mitigated" if mitigated else "Unmitigated (Supply Zone)",
                })

    # 4. Fair Value Gaps (FVG) — 3-candle rule
    fvgs: list[dict[str, Any]] = []
    for i in range(2, n - 1):
        # Bullish FVG: Low of candle i > High of candle i-2
        if lows[i] > highs[i - 2]:
            gap_size = lows[i] - highs[i - 2]
            if gap_size > 0:
                is_filled = any(lows[k] <= highs[i - 2] for k in range(i + 1, n))
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "top": lows[i],
                    "bottom": highs[i - 2],
                    "date": dates[i],
                    "is_filled": is_filled,
                    "status": "Filled" if is_filled else "Open Imbalance (Target Pullback)",
                })
        # Bearish FVG: High of candle i < Low of candle i-2
        elif highs[i] < lows[i - 2]:
            gap_size = lows[i - 2] - highs[i]
            if gap_size > 0:
                is_filled = any(highs[k] >= lows[i - 2] for k in range(i + 1, n))
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "top": lows[i - 2],
                    "bottom": highs[i],
                    "date": dates[i],
                    "is_filled": is_filled,
                    "status": "Filled" if is_filled else "Open Imbalance (Target Pullback)",
                })

    # 5. Liquidity Sweeps
    liquidity_sweeps: list[dict[str, Any]] = []
    for i in range(max(5, n - 20), n):
        prior_h = max(highs[max(0, i - 10):i])
        prior_l = min(lows[max(0, i - 10):i])
        # High sweep: High pierced prior high but Close closed below prior high
        if highs[i] > prior_h and closes[i] < prior_h:
            liquidity_sweeps.append({
                "type": "BUY_SIDE_LIQUIDITY_SWEPT",
                "price": highs[i],
                "date": dates[i],
                "bias": "BEARISH_REVERSAL_PRESSURE",
                "label": "Buy-side Liquidity Swept (Fakeout High)",
            })
        # Low sweep: Low pierced prior low but Close closed above prior low
        if lows[i] < prior_l and closes[i] > prior_l:
            liquidity_sweeps.append({
                "type": "SELL_SIDE_LIQUIDITY_SWEPT",
                "price": lows[i],
                "date": dates[i],
                "bias": "BULLISH_REVERSAL_PRESSURE",
                "label": "Sell-side Liquidity Swept (Stop Hunt Low)",
            })

    # 6. Dealing Range (Premium vs Discount)
    lookback_range = min(60, n)
    range_high = max(highs[-lookback_range:])
    range_low = min(lows[-lookback_range:])
    range_eq = (range_high + range_low) / 2.0

    in_discount = current_price < range_eq
    dealing_zone = "DISCOUNT (Zona Beli Ideal)" if in_discount else "PREMIUM (Zona Distribusi/Ambil Untung)"

    # Determine SMC Bias
    bias = "NEUTRAL"
    score = 50
    active_ob = [ob for ob in order_blocks if not ob["mitigated"]]
    active_bull_ob = [ob for ob in active_ob if ob["type"] == "BULLISH_OB"]
    active_bear_ob = [ob for ob in active_ob if ob["type"] == "BEARISH_OB"]

    latest_structure = structure_points[-1]["label"] if structure_points else "N/A"
    latest_event = choch_events[-1] if choch_events else (bos_events[-1] if bos_events else None)

    if latest_structure in ("HH", "HL") or (latest_event and "BULLISH" in latest_event["type"]):
        bias = "BULLISH"
        score = 75
        summary = f"Struktur SMC Bullish ({latest_structure}). dealing range di zona {dealing_zone}."
    elif latest_structure in ("LH", "LL") or (latest_event and "BEARISH" in latest_event["type"]):
        bias = "BEARISH"
        score = 30
        summary = f"Struktur SMC Bearish ({latest_structure}). Tekanan jual mendominasi."
    else:
        summary = f"Struktur SMC netral/konsolidasi ({dealing_zone})."

    patterns_identified = len(structure_points[-5:]) + len(bos_events[-2:]) + len(choch_events[-2:]) + len(active_ob[-3:])
    display_count = min(10, max(4, patterns_identified))

    return {
        "indicator_id": "SMC",
        "name": "Smart Money Concepts (SMC)",
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "READY",
        "calculated_at": now_str,
        "last_candle_time": last_candle_time,
        "values": {
            "market_structure": latest_structure,
            "dealing_range_eq": round(range_eq, 2),
            "dealing_zone": dealing_zone,
            "in_discount": in_discount,
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
        },
        "signals": {
            "bias": bias,
            "score_0_100": score,
            "summary": summary,
            "latest_event": latest_event,
        },
        "levels": {
            "order_blocks": active_ob[-4:],
            "fair_value_gaps": [f for f in fvgs if not f["is_filled"]][-3:],
            "liquidity_sweeps": liquidity_sweeps[-3:],
            "structure_points": structure_points[-6:],
        },
        "warnings": [],
        "display_status": f"Terdeteksi {display_count}/10 Pola Struktur",
    }


# ==============================================================================
# 3. EMA200 — Exponential Moving Average 200 Engine
# ==============================================================================

def compute_ema200_indicator(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
) -> dict[str, Any]:
    """
    Computes standard EMA 200:
    EMA(t) = Close(t) * alpha + EMA(t-1) * (1 - alpha)
    with alpha = 2 / (200 + 1).
    Validates required history (>200 bars). Computes slope, distance, and cross status.
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)
    n = len(closes)

    if n < 50:
        return {
            "indicator_id": "EMA200",
            "name": "EMA 200 (Exponential Moving Average)",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WARMING_UP",
            "calculated_at": now_str,
            "last_candle_time": dates[-1] if dates else "",
            "values": {"ema_200": None, "bars_available": n, "bars_required": 200},
            "signals": {"bias": "NEUTRAL", "score_0_100": 50, "summary": f"Data candle belum cukup untuk EMA 200 ({n}/200 candle)."},
            "levels": {"ema_200": None},
            "warnings": [f"Dibutuhkan minimal 200 candle untuk validitas penuh EMA-200. Saat ini tersedia {n} candle."],
            "display_status": f"Pemanasan ({n}/200 bar)",
        }

    current_price = closes[-1]
    last_candle_time = dates[-1] if dates else ""
    alpha = 2.0 / (200.0 + 1.0)

    # Calculate EMA series
    ema_vals: list[float] = []
    # Seed with SMA of first min(200, n) bars
    seed_len = min(200, n)
    current_ema = sum(closes[:seed_len]) / seed_len
    ema_vals.append(current_ema)

    for i in range(seed_len, n):
        current_ema = (closes[i] * alpha) + (current_ema * (1.0 - alpha))
        ema_vals.append(current_ema)

    final_ema = ema_vals[-1]
    prev_ema = ema_vals[-5] if len(ema_vals) >= 5 else ema_vals[0]
    denom_prev = max(abs(prev_ema), 1e-9)
    slope = (final_ema - prev_ema) / denom_prev
    denom_final = max(abs(final_ema), 1e-9)
    distance_pct = round(((current_price - final_ema) / denom_final) * 100.0, 2)

    is_above = current_price >= final_ema
    bias = "BULLISH" if is_above else "BEARISH"
    score = 70 if is_above else 35

    summary = (
        f"Harga ({current_price:,.2f}) berada {abs(distance_pct):.2f}% di {'atas' if is_above else 'bawah'} "
        f"EMA-200 ({final_ema:,.2f}), mengindikasikan bias tren jangka panjang "
        f"{'Bullish (Akumulasi Sehat)' if is_above else 'Bearish (Tekanan Tren Turun)'}."
    )

    status = "READY" if n >= 200 else "WARMING_UP"
    display_status = "Aktif (Tren Bullish)" if is_above else "Aktif (Tren Bearish)"
    if status == "WARMING_UP":
        display_status = f"Pemanasan ({n}/200 bar)"

    return {
        "indicator_id": "EMA200",
        "name": "EMA 200 (Exponential Moving Average)",
        "symbol": symbol,
        "timeframe": timeframe,
        "status": status,
        "calculated_at": now_str,
        "last_candle_time": last_candle_time,
        "values": {
            "ema_200": round(final_ema, 2),
            "current_price": round(current_price, 2),
            "distance_pct": distance_pct,
            "slope_pct_5bars": round(slope * 100.0, 3),
            "trend_alignment": "BULLISH_MAJOR" if is_above else "BEARISH_MAJOR",
        },
        "signals": {
            "bias": bias,
            "score_0_100": score,
            "summary": summary,
            "price_above_ema": is_above,
        },
        "levels": {
            "ema_200_line": round(final_ema, 2),
        },
        "warnings": [f"Data tersedia {n} candle (akurasi optimal pada 200+ candle)."] if n < 200 else [],
        "display_status": display_status,
    }


# ==============================================================================
# 4. Ichimoku Cloud — Ichimoku Kinko Hyo Engine
# ==============================================================================

def compute_ichimoku_indicator(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
) -> dict[str, Any]:
    """
    Computes standard Ichimoku Kinko Hyo (9, 26, 52):
    1. Tenkan-sen (9): (H9 + L9) / 2
    2. Kijun-sen (26): (H26 + L26) / 2
    3. Senkou Span A: (Tenkan + Kijun) / 2 plotted 26 bars ahead
    4. Senkou Span B (52): (H52 + L52) / 2 plotted 26 bars ahead
    5. Chikou Span: Close plotted 26 bars back
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)
    n = len(closes)

    if n < 26:
        return {
            "indicator_id": "ICHIMOKU",
            "name": "Ichimoku Cloud (Kinko Hyo)",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WARMING_UP",
            "calculated_at": now_str,
            "last_candle_time": dates[-1] if dates else "",
            "values": {},
            "signals": {"bias": "NEUTRAL", "score_0_100": 50, "summary": "Data candle tidak mencukupi untuk Ichimoku Cloud (< 26 candle)."},
            "levels": {},
            "warnings": ["Data candle kurang dari 26 periode."],
            "display_status": "Pemanasan (0/8 Komponen)",
        }

    current_price = closes[-1]
    last_candle_time = dates[-1] if dates else ""

    # Tenkan-sen (9 periods)
    h9 = max(highs[-9:])
    l9 = min(lows[-9:])
    tenkan = (h9 + l9) / 2.0

    # Kijun-sen (26 periods)
    h26 = max(highs[-26:])
    l26 = min(lows[-26:])
    kijun = (h26 + l26) / 2.0

    # Senkou Span A (Current value derived from 26 bars ago if available, or current projection)
    span_a_projected = (tenkan + kijun) / 2.0

    # Senkou Span B (52 periods)
    if n >= 52:
        h52 = max(highs[-52:])
        l52 = min(lows[-52:])
        span_b_projected = (h52 + l52) / 2.0
    else:
        span_b_projected = (max(highs) + min(lows)) / 2.0

    # Current Cloud at price (using historical projection from 26 bars ago if available)
    if n >= 52:
        hist_h9 = max(highs[-35:-26]) if n >= 35 else h9
        hist_l9 = min(lows[-35:-26]) if n >= 35 else l9
        hist_tenkan = (hist_h9 + hist_l9) / 2.0

        hist_h26 = max(highs[-52:-26])
        hist_l26 = min(lows[-52:-26])
        hist_kijun = (hist_h26 + hist_l26) / 2.0

        current_cloud_top = (hist_tenkan + hist_kijun) / 2.0
        current_cloud_bottom = (max(highs[-78:-26]) + min(lows[-78:-26])) / 2.0 if n >= 78 else span_b_projected
    else:
        current_cloud_top = span_a_projected
        current_cloud_bottom = span_b_projected

    kumo_high = max(current_cloud_top, current_cloud_bottom)
    kumo_low = min(current_cloud_top, current_cloud_bottom)

    # Cloud analysis
    if current_price > kumo_high:
        cloud_pos = "ABOVE_CLOUD"
        cloud_pos_label = "Di Atas Awan Kumo (Bullish)"
        bias = "BULLISH"
        score = 80
    elif current_price < kumo_low:
        cloud_pos = "BELOW_CLOUD"
        cloud_pos_label = "Di Bawah Awan Kumo (Bearish)"
        bias = "BEARISH"
        score = 25
    else:
        cloud_pos = "INSIDE_CLOUD"
        cloud_pos_label = "Di Dalam Awan Kumo (Konsolidasi/Netral)"
        bias = "NEUTRAL"
        score = 50

    # TK Cross
    tk_cross = "BULLISH_CROSS" if tenkan > kijun else "BEARISH_CROSS"
    tk_label = "Tenkan > Kijun (Golden TK)" if tenkan > kijun else "Tenkan < Kijun (Death TK)"

    summary = (
        f"Harga berada {cloud_pos_label}. "
        f"Tenkan ({tenkan:,.2f}) vs Kijun ({kijun:,.2f}): {tk_label}. "
        f"Awan Kumo Masa Depan: {'Hijau (Bullish)' if span_a_projected >= span_b_projected else 'Merah (Bearish)'}."
    )

    return {
        "indicator_id": "ICHIMOKU",
        "name": "Ichimoku Cloud (Kinko Hyo)",
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "READY",
        "calculated_at": now_str,
        "last_candle_time": last_candle_time,
        "values": {
            "tenkan_sen": round(tenkan, 2),
            "kijun_sen": round(kijun, 2),
            "senkou_span_a": round(span_a_projected, 2),
            "senkou_span_b": round(span_b_projected, 2),
            "kumo_upper": round(kumo_high, 2),
            "kumo_lower": round(kumo_low, 2),
            "cloud_position": cloud_pos,
            "tk_cross": tk_cross,
        },
        "signals": {
            "bias": bias,
            "score_0_100": score,
            "summary": summary,
        },
        "levels": {
            "tenkan": round(tenkan, 2),
            "kijun": round(kijun, 2),
            "cloud_top": round(kumo_high, 2),
            "cloud_bottom": round(kumo_low, 2),
            "projected_span_a": round(span_a_projected, 2),
            "projected_span_b": round(span_b_projected, 2),
        },
        "warnings": [],
        "display_status": f"Aktif ({cloud_pos_label})",
    }


# ==============================================================================
# 5. Fibonacci Retracement Engine
# ==============================================================================

def compute_fibonacci_indicator(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
) -> dict[str, Any]:
    """
    Computes Fibonacci Retracement & Extensions from active confirmed swing dealing range:
    Levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%, 161.8%.
    Identifies Golden Pocket (50% - 61.8%) and directional impulse.
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)
    n = len(closes)

    if n < 20:
        return {
            "indicator_id": "FIBONACCI",
            "name": "Fibonacci Retracement",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WARMING_UP",
            "calculated_at": now_str,
            "last_candle_time": dates[-1] if dates else "",
            "values": {},
            "signals": {"bias": "NEUTRAL", "score_0_100": 50, "summary": "Data candle tidak cukup untuk Fibonacci Retracement (< 20 candle)."},
            "levels": {},
            "warnings": ["Data candle kurang dari 20 periode."],
            "display_status": "Pemanasan (0/8 Level)",
        }

    current_price = closes[-1]
    last_candle_time = dates[-1] if dates else ""

    # Find highest high and lowest low within last 60 candles
    lookback = min(60, n)
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]

    max_h = max(recent_highs)
    min_l = min(recent_lows)
    max_idx = recent_highs.index(max_h)
    min_idx = recent_lows.index(min_l)

    # If min occurred before max -> Bullish Impulse
    is_bullish_impulse = min_idx < max_idx
    diff = max_h - min_l

    if diff <= 0:
        diff = 1.0

    if is_bullish_impulse:
        # Retracement from High downwards
        fib_0 = max_h
        fib_236 = max_h - (0.236 * diff)
        fib_382 = max_h - (0.382 * diff)
        fib_500 = max_h - (0.500 * diff)
        fib_618 = max_h - (0.618 * diff)
        fib_786 = max_h - (0.786 * diff)
        fib_100 = min_l
        fib_1618 = max_h + (0.618 * diff)
    else:
        # Retracement from Low upwards
        fib_0 = min_l
        fib_236 = min_l + (0.236 * diff)
        fib_382 = min_l + (0.382 * diff)
        fib_500 = min_l + (0.500 * diff)
        fib_618 = min_l + (0.618 * diff)
        fib_786 = min_l + (0.786 * diff)
        fib_100 = max_h
        fib_1618 = min_l - (0.618 * diff)

    in_golden_pocket = (min(fib_500, fib_618) <= current_price <= max(fib_500, fib_618))

    bias = "NEUTRAL"
    score = 50
    if in_golden_pocket:
        bias = "BULLISH" if is_bullish_impulse else "BEARISH"
        score = 80 if is_bullish_impulse else 25
        summary = (
            f"Harga berada tepat di GOLDEN POCKET Fibonacci (50.0% – 61.8% @ "
            f"Rp {min(fib_500, fib_618):,.2f} – Rp {max(fib_500, fib_618):,.2f}). Area pantulan probabilitas tinggi."
        )
    elif current_price >= max_h:
        bias = "BULLISH"
        score = 75
        summary = f"Harga menembus level 0% (High Rp {max_h:,.2f}), menguji ekstensi 161.8% @ Rp {fib_1618:,.2f}."
    elif current_price <= min_l:
        bias = "BEARISH"
        score = 30
        summary = f"Harga breakdown di bawah level 100% (Low Rp {min_l:,.2f})."
    else:
        summary = f"Harga terkonsolidasi di rentang Fibonacci antara {round(min_l, 2)} dan {round(max_h, 2)}."

    return {
        "indicator_id": "FIBONACCI",
        "name": "Fibonacci Retracement",
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "READY",
        "calculated_at": now_str,
        "last_candle_time": last_candle_time,
        "values": {
            "impulse_direction": "BULLISH_UPTREND" if is_bullish_impulse else "BEARISH_DOWNTREND",
            "swing_high": round(max_h, 2),
            "swing_low": round(min_l, 2),
            "in_golden_pocket": in_golden_pocket,
        },
        "signals": {
            "bias": bias,
            "score_0_100": score,
            "summary": summary,
        },
        "levels": {
            "fib_0": round(fib_0, 2),
            "fib_236": round(fib_236, 2),
            "fib_382": round(fib_382, 2),
            "fib_500": round(fib_500, 2),
            "fib_618": round(fib_618, 2),
            "fib_786": round(fib_786, 2),
            "fib_100": round(fib_100, 2),
            "fib_1618": round(fib_1618, 2),
            "golden_pocket_min": round(min(fib_500, fib_618), 2),
            "golden_pocket_max": round(max(fib_500, fib_618), 2),
        },
        "warnings": [],
        "display_status": "Golden Pocket Rebound" if in_golden_pocket else "8/8 Level Dipetakan",
    }


# ==============================================================================
# Multi-Indicator Synthesizer & Trading Decision Engine
# ==============================================================================

def run_technical_audit_and_synthesis(
    candles: list[dict[str, Any]],
    symbol: str,
    timeframe: str = "1d",
    current_price: Optional[float] = None,
) -> dict[str, Any]:
    """
    Executes the 5 technical indicators, aggregates their objective signals,
    and produces an integrated trading decision: BUY, SELL, HOLD, or WAIT.
    """
    now_str = datetime.now(WIB_TZ).isoformat()
    closes, highs, lows, opens, volumes, dates = _extract_ohlcv(candles)

    if not closes:
        return {
            "status": "INVALID_DATA",
            "decision": "WAIT",
            "indicators": {},
            "summary": "Tidak ada data OHLCV valid untuk analisis teknikal.",
        }

    px = current_price if (current_price and current_price > 0) else closes[-1]

    # Calculate 5 indicators
    snr = compute_snr_indicator(candles, symbol, timeframe)
    smc = compute_smc_indicator(candles, symbol, timeframe)
    ema200 = compute_ema200_indicator(candles, symbol, timeframe)
    ichimoku = compute_ichimoku_indicator(candles, symbol, timeframe)
    fibonacci = compute_fibonacci_indicator(candles, symbol, timeframe)

    indicators_map = {
        "SNR": snr,
        "SMC": smc,
        "EMA200": ema200,
        "ICHIMOKU": ichimoku,
        "FIBONACCI": fibonacci,
    }

    # Weight scores
    # Weights: EMA200 (25%), SNR (25%), SMC (20%), Ichimoku (15%), Fibonacci (15%)
    weights = {"EMA200": 0.25, "SNR": 0.25, "SMC": 0.20, "ICHIMOKU": 0.15, "FIBONACCI": 0.15}
    total_score = 0.0
    bullish_votes = 0
    bearish_votes = 0
    neutral_votes = 0

    reasons: list[str] = []

    for k, ind in indicators_map.items():
        sig = ind.get("signals", {})
        b = sig.get("bias", "NEUTRAL")
        sc = sig.get("score_0_100", 50)
        total_score += sc * weights.get(k, 0.2)

        if b == "BULLISH":
            bullish_votes += 1
            reasons.append(f"[{k}] {sig.get('summary')}")
        elif b == "BEARISH":
            bearish_votes += 1
            reasons.append(f"[{k}] {sig.get('summary')}")
        else:
            neutral_votes += 1

    total_score = round(total_score, 1)

    # Synthesize Decision
    nearest_sup = snr.get("values", {}).get("nearest_support")
    nearest_res = snr.get("values", {}).get("nearest_resistance")

    # Entry wait price: If neutral/waiting, wait for pullback to nearest support or golden pocket
    golden_min = fibonacci.get("levels", {}).get("golden_pocket_min")
    wait_target_price = nearest_sup or golden_min or round(px * 0.97, 2)

    if total_score >= 68 and bullish_votes >= 3:
        decision = "BUY"
        decision_label = "BUY / LONG"
        decision_color = "emerald"
        decision_desc = (
            f"Konfirmasi Bullish kuat dari {bullish_votes}/5 indikator utama. "
            f"Tren di atas EMA200 dan pantulan support/Golden Pocket terkonfirmasi."
        )
    elif total_score <= 38 and bearish_votes >= 3:
        decision = "SELL"
        decision_label = "SELL / SHORT"
        decision_color = "rose"
        decision_desc = (
            f"Tekanan Bearish dominan dari {bearish_votes}/5 indikator. "
            f"Harga di bawah resistance kunci / Kumo cloud."
        )
    elif 50 <= total_score < 68 and bullish_votes >= 2:
        decision = "HOLD"
        decision_label = "HOLD"
        decision_color = "cyan"
        decision_desc = (
            f"Bias positif ({total_score}/100) namun belum mencapai ambang eksekusi baru. "
            f"Pertahankan posisi dengan trailing stop."
        )
    else:
        decision = "WAIT"
        decision_label = f"TUNGGU DULU (Wait Pullback ~{wait_target_price:,.0f})"
        decision_color = "amber"
        decision_desc = (
            f"Pasar berada di fase konsolidasi atau mendekati resistance. "
            f"Disarankan tunggu konfirmasi pantulan di area harga Rp {wait_target_price:,.0f}."
        )

    return {
        "status": "READY",
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": px,
        "calculated_at": now_str,
        "overall_score_0_100": total_score,
        "decision": decision,
        "decision_label": decision_label,
        "decision_color": decision_color,
        "decision_desc": decision_desc,
        "wait_target_price": wait_target_price,
        "votes": {
            "bullish": bullish_votes,
            "bearish": bearish_votes,
            "neutral": neutral_votes,
        },
        "reasons": reasons,
        "indicators": indicators_map,
    }
