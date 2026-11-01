"""
Adaptive Profit Manager for SOFIA MEME BOT V2.
Maintains state for active positions:
- Highest observed price (Peak)
- Lowest observed price (Trough) for MAE
- Ratcheted trailing stop price (Invariant: NEVER moves downward)
- Break-even protection flag
Fulfills PRD Section 6.3 & 6.4 and Directive Section 5.
"""

import logging
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import PortfolioHolding
from app.v2.core.exit_policy import exit_policy, PolicyCheckResult

logger = logging.getLogger("sofia.v2.adaptive_profit_manager")

# In-memory caches for high-frequency tracking (persisted during holding updates)
_PEAK_PRICES: Dict[str, float] = {}
_TROUGH_PRICES: Dict[str, float] = {}
_TRAILING_STOPS: Dict[str, float] = {}
_BREAKEVEN_FLAGS: Dict[str, bool] = {}


class AdaptiveProfitManager:
    """
    Manages trailing stops, peak excursions, and break-even ratchets.
    """

    @classmethod
    def update_position_tracking(
        cls,
        symbol: str,
        current_price: float,
        entry_price: float,
    ) -> Tuple[float, float, Optional[float], bool]:
        """
        Updates peak and trough observed prices and ratchets trailing stop.
        Returns: (highest, lowest, trailing_stop, be_active)
        """
        key = symbol.upper()
        if key not in _PEAK_PRICES or current_price > _PEAK_PRICES[key]:
            _PEAK_PRICES[key] = max(current_price, entry_price)

        if key not in _TROUGH_PRICES or current_price < _TROUGH_PRICES[key]:
            _TROUGH_PRICES[key] = min(current_price, entry_price)

        highest = _PEAK_PRICES[key]
        lowest = _TROUGH_PRICES[key]
        existing_trail = _TRAILING_STOPS.get(key)
        be_active = _BREAKEVEN_FLAGS.get(key, False)

        # Evaluate policy for trailing stop updates
        policy_res = exit_policy.evaluate_position_policy(
            entry_price=entry_price,
            current_price=current_price,
            highest_price=highest,
            current_trailing_stop=existing_trail,
            breakeven_activated=be_active,
            liquidity_decay_pct=0.0,
        )

        new_trail = policy_res.trailing_stop_price
        if new_trail is not None:
            # Enforce Invariant: Trailing stop can NEVER move downward
            if existing_trail is None or new_trail > existing_trail:
                _TRAILING_STOPS[key] = new_trail
                existing_trail = new_trail

        if policy_res.breakeven_triggered:
            _BREAKEVEN_FLAGS[key] = True
            be_active = True

        return highest, lowest, existing_trail, be_active

    @classmethod
    def get_position_tracking(cls, symbol: str) -> Tuple[float, float, Optional[float], bool]:
        """
        Retrieves current tracked excursions without mutating state.
        Returns: (highest, lowest, trailing_stop, be_active)
        """
        key = symbol.upper()
        highest = _PEAK_PRICES.get(key, 0.0)
        lowest = _TROUGH_PRICES.get(key, 0.0)
        current_trail = _TRAILING_STOPS.get(key)
        be_active = _BREAKEVEN_FLAGS.get(key, False)
        return highest, lowest, current_trail, be_active

    @classmethod
    def set_trailing_stop(cls, symbol: str, stop_price: float, be_active: bool = False):
        key = symbol.upper()
        # Invariant: trailing stop can NEVER move down
        existing = _TRAILING_STOPS.get(key)
        if existing is None or stop_price > existing:
            _TRAILING_STOPS[key] = stop_price
        if be_active:
            _BREAKEVEN_FLAGS[key] = True

    @classmethod
    def clear_position(cls, symbol: str):
        key = symbol.upper()
        _PEAK_PRICES.pop(key, None)
        _TROUGH_PRICES.pop(key, None)
        _TRAILING_STOPS.pop(key, None)
        _BREAKEVEN_FLAGS.pop(key, None)


# Singleton
adaptive_profit_manager = AdaptiveProfitManager()
