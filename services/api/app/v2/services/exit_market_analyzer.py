"""
Exit Market Analyzer for SOFIA MEME BOT V2.
Evaluates market momentum deterioration, sell pressure, and orderbook liquidity decay.
Fulfills PRD Section 6.2 & Directive Section 3/4.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("sofia.v2.exit_market_analyzer")


class ExitMarketAnalyzer:
    """
    Analyzes price momentum decay, sell pressure, liquidity deterioration,
    and market structure degradation for an open position.
    """

    @classmethod
    def analyze_market_conditions(
        cls,
        token_data: Dict[str, Any],
        entry_price: float,
        current_price: float,
        highest_price: float,
        entry_liquidity: float,
        current_liquidity: float,
        position_age_minutes: float,
    ) -> Dict[str, Any]:
        """
        Analyzes real-time market data to detect deterioration signs.
        Missing data is NEVER interpreted as safe!
        """
        p5m = float(token_data.get("price_change_5m_pct") or token_data.get("price_change_5m") or 0.0)
        p1h = float(token_data.get("price_change_1h_pct") or token_data.get("price_change_1h") or 0.0)
        v5m = float(token_data.get("volume_5m_usd") or token_data.get("volume_5m") or 0.0)
        v1h = float(token_data.get("volume_1h_usd") or token_data.get("volume_1h") or 0.0)

        txns = token_data.get("txns") or {}
        txns_5m = txns.get("m5") or txns.get("5m") or {}
        buys_5m = int(txns_5m.get("buys") or token_data.get("buys_5m") or 0)
        sells_5m = int(txns_5m.get("sells") or token_data.get("sells_5m") or 0)
        tot_tx_5m = buys_5m + sells_5m

        # 1. Momentum Condition
        # Retracement from peak
        peak_retracement_pct = 0.0
        if highest_price > 0:
            peak_retracement_pct = max(0.0, ((highest_price - current_price) / highest_price) * 100.0)

        expected_5m_vol = (v1h / 12.0) if v1h > 0 else 1.0
        volume_velocity = (v5m / expected_5m_vol) if expected_5m_vol > 0 else 0.0

        if p5m <= -12.0 or peak_retracement_pct >= 25.0:
            momentum = "collapsed"
        elif p5m < -3.0 or peak_retracement_pct >= 12.0 or volume_velocity < 0.4:
            momentum = "weakening"
        elif p5m >= 4.0 and volume_velocity >= 1.2:
            momentum = "strengthening"
        else:
            momentum = "stable"

        # 2. Sell Pressure Condition
        sell_ratio = (sells_5m / tot_tx_5m) if tot_tx_5m > 0 else 0.5
        if sell_ratio >= 0.70 and sells_5m >= 15:
            sell_pressure = "dominant"
        elif sell_ratio >= 0.55:
            sell_pressure = "increasing"
        elif sell_ratio <= 0.35:
            sell_pressure = "low"
        else:
            sell_pressure = "normal"

        # 3. Liquidity Deterioration
        liq_decay_pct = 0.0
        if entry_liquidity > 0:
            liq_decay_pct = max(0.0, ((entry_liquidity - current_liquidity) / entry_liquidity) * 100.0)

        if current_liquidity <= 1000.0 or liq_decay_pct >= 50.0:
            liquidity_status = "critical_drop"
        elif liq_decay_pct >= 20.0 or current_liquidity < 4000.0:
            liquidity_status = "decaying"
        elif current_liquidity >= 30000.0:
            liquidity_status = "deep"
        else:
            liquidity_status = "stable"

        return {
            "momentum": momentum,
            "sell_pressure": sell_pressure,
            "liquidity": liquidity_status,
            "peak_retracement_pct": round(peak_retracement_pct, 2),
            "liquidity_decay_pct": round(liq_decay_pct, 2),
            "volume_velocity": round(volume_velocity, 2),
            "sell_ratio_5m": round(sell_ratio * 100.0, 1),
            "buys_5m": buys_5m,
            "sells_5m": sells_5m,
            "price_change_5m_pct": p5m,
            "price_change_1h_pct": p1h,
            "position_age_minutes": round(position_age_minutes, 1),
        }


# Singleton
exit_market_analyzer = ExitMarketAnalyzer()
