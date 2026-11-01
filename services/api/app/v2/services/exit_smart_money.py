"""
Exit Smart Money Tracker for SOFIA MEME BOT V2.
Evaluates whale distribution, wallet cluster dumps, and smart money exit signals.
Fulfills PRD Section 4.4 & Directive Section 3/4.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("sofia.v2.exit_smart_money")


class ExitSmartMoneyTracker:
    """
    Evaluates whale and insider wallet behavior to detect coordinated distribution.
    """

    @classmethod
    def evaluate_smart_money_activity(
        cls,
        token_data: Dict[str, Any],
        top10_concentration_pct: float,
        dev_holding_pct: float,
    ) -> Dict[str, Any]:
        """
        Evaluates whether smart money is accumulating, holding, distributing, or dumping.
        """
        txns = token_data.get("txns") or {}
        txns_5m = txns.get("m5") or txns.get("5m") or {}
        buys_5m = int(txns_5m.get("buys") or 0)
        sells_5m = int(txns_5m.get("sells") or 0)
        tot_tx = buys_5m + sells_5m
        sell_ratio = (sells_5m / tot_tx) if tot_tx > 0 else 0.5

        # Check for abnormal large sell dominance
        whale_dump_detected = False
        large_sells_count = int(token_data.get("large_sells_5m") or 0)

        if sell_ratio >= 0.75 and sells_5m >= 15:
            smart_money_status = "dumping"
            whale_dump_detected = True
        elif sell_ratio >= 0.60 or dev_holding_pct > 12.0 or large_sells_count >= 3:
            smart_money_status = "distribution"
        elif sell_ratio <= 0.35 and buys_5m >= 10:
            smart_money_status = "accumulation"
        else:
            smart_money_status = "holding"

        return {
            "smart_money_status": smart_money_status,
            "whale_dump_detected": whale_dump_detected,
            "top10_concentration_pct": top10_concentration_pct,
            "dev_holding_pct": dev_holding_pct,
            "sell_ratio_5m": round(sell_ratio * 100.0, 1),
        }


# Singleton
exit_smart_money = ExitSmartMoneyTracker()
