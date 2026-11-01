"""
Exit Policy & Deterministic Risk Invariants for SOFIA MEME BOT V2.
Strictly adheres to:
- PRD Section 6 (AI Exit Intelligence & Adaptive Profit Management)
- Directive Section 5 (Adaptive Profit Management) & Section 7 (Safety Requirements)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger("sofia.v2.exit_policy")


class PolicyCheckResult(BaseModel):
    action: str  # HOLD, TIGHTEN_STOP, REDUCE_25, REDUCE_50, REDUCE_75, FULL_EXIT, EMERGENCY_EXIT
    suggested_sell_pct: int  # 0, 25, 50, 75, 100
    is_hard_override: bool
    override_reason: Optional[str] = None
    trailing_stop_price: Optional[float] = None
    breakeven_triggered: bool = False


class ExitPolicy:
    """
    Enforces deterministic profit protection and risk rules.
    AI proposes market interpretations, but Deterministic Exit Policy holds absolute safety authority.
    """

    DEFAULT_HARD_STOP_PCT = -12.0
    BREAKEVEN_ACTIVATION_PROFIT_PCT = 20.0
    TRAILING_GAP_PCT = 8.0  # Trails 8% below peak price once trailing is active

    @classmethod
    def evaluate_position_policy(
        cls,
        entry_price: float,
        current_price: float,
        highest_price: float,
        current_trailing_stop: Optional[float],
        breakeven_activated: bool,
        liquidity_decay_pct: float,
        is_honeypot: bool = False,
        strategy_mode: str = "DEFAULT",
    ) -> PolicyCheckResult:
        """
        Evaluates deterministic invariants.
        Returns PolicyCheckResult.
        """
        if entry_price <= 0:
            return PolicyCheckResult(action="HOLD", suggested_sell_pct=0, is_hard_override=False)

        current_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
        peak_pnl_pct = ((highest_price - entry_price) / entry_price) * 100.0 if highest_price > 0 else current_pnl_pct

        # 1. Mandatory Emergency Exit (Honeypot or Critical Liquidity Collapse)
        if is_honeypot:
            return PolicyCheckResult(
                action="EMERGENCY_EXIT",
                suggested_sell_pct=100,
                is_hard_override=True,
                override_reason="EMERGENCY: Honeypot terdeteksi on-chain!",
            )

        if liquidity_decay_pct >= 50.0:
            return PolicyCheckResult(
                action="EMERGENCY_EXIT",
                suggested_sell_pct=100,
                is_hard_override=True,
                override_reason=f"EMERGENCY: Kolaps likuiditas pool (-{liquidity_decay_pct:.1f}%)!",
            )

        # 2. Hard Stop-Loss Override (Deterministic protection overrides any AI HOLD)
        hard_stop_thresh = cls.DEFAULT_HARD_STOP_PCT
        if strategy_mode.upper() == "SAFE":
            hard_stop_thresh = -8.0
        elif strategy_mode.upper() == "AGGRESSIVE":
            hard_stop_thresh = -15.0

        if current_pnl_pct <= hard_stop_thresh:
            return PolicyCheckResult(
                action="FULL_EXIT",
                suggested_sell_pct=100,
                is_hard_override=True,
                override_reason=f"HARD_STOP_TRIGGERED: Rugi posisi ({current_pnl_pct:.2f}%) menyentuh batas ({hard_stop_thresh:.1f}%)!",
            )

        # 3. Trailing Stop Calculation & Ratchet
        # Invariant: Trailing stop price can NEVER move down (never increases max permitted loss)
        new_trailing_stop = current_trailing_stop
        new_be_activated = breakeven_activated

        # Break-even protection: If peak reached +20%, stop is ratcheted to entry price + 1.0% (covers fees)
        if peak_pnl_pct >= cls.BREAKEVEN_ACTIVATION_PROFIT_PCT:
            new_be_activated = True
            be_price = entry_price * 1.01
            if new_trailing_stop is None or be_price > new_trailing_stop:
                new_trailing_stop = be_price

        # Trailing stop update from peak
        if peak_pnl_pct >= 25.0:
            calculated_trail_price = highest_price * (1.0 - (cls.TRAILING_GAP_PCT / 100.0))
            if new_trailing_stop is None or calculated_trail_price > new_trailing_stop:
                new_trailing_stop = calculated_trail_price

        # Check if current price violated active trailing stop
        if new_trailing_stop and current_price <= new_trailing_stop:
            return PolicyCheckResult(
                action="FULL_EXIT",
                suggested_sell_pct=100,
                is_hard_override=True,
                override_reason=f"TRAILING_STOP_TRIGGERED: Harga ${current_price:.8f} menembus batas trailing stop ${new_trailing_stop:.8f}!",
                trailing_stop_price=new_trailing_stop,
                breakeven_triggered=new_be_activated,
            )

        # 4. Adaptive Partial Take Profit Targets
        if current_pnl_pct >= 150.0:
            return PolicyCheckResult(
                action="REDUCE_75",
                suggested_sell_pct=75,
                is_hard_override=False,
                trailing_stop_price=new_trailing_stop,
                breakeven_triggered=new_be_activated,
            )
        elif current_pnl_pct >= 80.0:
            return PolicyCheckResult(
                action="REDUCE_50",
                suggested_sell_pct=50,
                is_hard_override=False,
                trailing_stop_price=new_trailing_stop,
                breakeven_triggered=new_be_activated,
            )
        elif current_pnl_pct >= 40.0:
            return PolicyCheckResult(
                action="REDUCE_25",
                suggested_sell_pct=25,
                is_hard_override=False,
                trailing_stop_price=new_trailing_stop,
                breakeven_triggered=new_be_activated,
            )

        return PolicyCheckResult(
            action="HOLD",
            suggested_sell_pct=0,
            is_hard_override=False,
            trailing_stop_price=new_trailing_stop,
            breakeven_triggered=new_be_activated,
        )


# Singleton
exit_policy = ExitPolicy()
