"""
Position State Machine for SOFIA MEME BOT V2.
Enforces the 8 formal lifecycle states and transition invariants.
Strictly adheres to:
- PRD Section 7.1 (Position Lifecycle)
- PRD Section 7.2 (Position Data)
- PRD Section 7.3 (Position Monitoring)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel

from app.v2.ai.schemas import PositionLifecycleState, PositionStateInfo

logger = logging.getLogger("sofia.v2.position_state_machine")


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""
    pass


class PositionStateMachine:
    """
    Manages deterministic lifecycle state transitions for positions.
    Guarantees that positions cannot skip critical verification steps
    (e.g. Cannot reach CLOSED without passing RECONCILIATION).
    """

    VALID_STATES: Set[PositionLifecycleState] = {
        "DISCOVERED",
        "ENTRY_APPROVED",
        "BUY_PENDING",
        "POSITION_OPEN",
        "MONITORING",
        "SELL_PENDING",
        "RECONCILIATION",
        "CLOSED",
    }

    # Allowed forward and backward transitions
    ALLOWED_TRANSITIONS: Dict[PositionLifecycleState, Set[PositionLifecycleState]] = {
        "DISCOVERED": {"ENTRY_APPROVED", "CLOSED"},
        "ENTRY_APPROVED": {"BUY_PENDING", "CLOSED"},
        "BUY_PENDING": {"POSITION_OPEN", "CLOSED"},
        "POSITION_OPEN": {"MONITORING"},
        "MONITORING": {"MONITORING", "SELL_PENDING", "RECONCILIATION"},
        "SELL_PENDING": {"RECONCILIATION", "MONITORING"},
        "RECONCILIATION": {"CLOSED", "MONITORING"},
        "CLOSED": set(),  # Terminal state
    }

    def __init__(self):
        # In-memory position state table keyed by position_id / symbol
        self._positions: Dict[str, PositionStateInfo] = {}

    def get_or_create_position(
        self,
        symbol: str,
        mint: str,
        mode: str = "PAPER",
        position_id: Optional[str] = None,
        initial_quantity: float = 0.0,
        entry_price: float = 0.0,
        initial_state: PositionLifecycleState = "DISCOVERED",
    ) -> PositionStateInfo:
        """
        Gets existing position tracker or initializes a new one.
        """
        key = f"{mode.upper()}:{symbol.upper()}"
        pos_id = position_id or key
        if key not in self._positions:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._positions[key] = PositionStateInfo(
                position_id=pos_id,
                symbol=symbol.upper(),
                mint=mint,
                mode=mode.upper(),
                current_state=initial_state,
                quantity=initial_quantity,
                remaining_quantity=initial_quantity,
                avg_entry_price=entry_price,
                current_price=entry_price,
                highest_price=entry_price,
                created_at=now_iso,
                updated_at=now_iso,
                transition_history=[{
                    "from_state": None,
                    "to_state": initial_state,
                    "reason": "INITIAL_CREATION",
                    "timestamp": now_iso,
                }],
            )
        return self._positions[key]

    def get_position(self, symbol: str, mode: str = "PAPER") -> Optional[PositionStateInfo]:
        key = f"{mode.upper()}:{symbol.upper()}"
        return self._positions.get(key)

    def list_positions(self, mode: Optional[str] = None) -> List[PositionStateInfo]:
        if mode:
            m = mode.upper()
            return [p for p in self._positions.values() if p.mode == m]
        return list(self._positions.values())

    def transition_to(
        self,
        symbol: str,
        new_state: PositionLifecycleState,
        reason: str,
        mode: str = "PAPER",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PositionStateInfo:
        """
        Transitions position to a new lifecycle state if valid.
        Raises InvalidStateTransitionError if the transition is prohibited.
        """
        key = f"{mode.upper()}:{symbol.upper()}"
        pos = self._positions.get(key)
        if not pos:
            raise KeyError(f"Position {key} is not registered in PositionStateMachine.")

        current = pos.current_state

        if new_state not in self.VALID_STATES:
            raise InvalidStateTransitionError(f"Unknown state: '{new_state}'.")

        allowed = self.ALLOWED_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"ILLEGAL_TRANSITION: Cannot transition position '{symbol}' from '{current}' to '{new_state}'. "
                f"Permitted next states: {list(allowed)}."
            )

        # Invariant 2: Cannot transition to CLOSED directly from MONITORING or SELL_PENDING without RECONCILIATION
        if new_state == "CLOSED" and current not in ("RECONCILIATION", "DISCOVERED", "ENTRY_APPROVED", "BUY_PENDING"):
            raise InvalidStateTransitionError(
                f"RECONCILIATION_REQUIRED: Position '{symbol}' must enter 'RECONCILIATION' before reaching 'CLOSED'."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        pos.current_state = new_state
        pos.updated_at = now_iso

        transition_entry = {
            "from_state": current,
            "to_state": new_state,
            "reason": reason,
            "timestamp": now_iso,
            "metadata": metadata or {},
        }
        pos.transition_history.append(transition_entry)

        logger.info(f"[POSITION STATE] {key}: {current} -> {new_state} (Reason: {reason})")
        return pos

    def update_metrics(
        self,
        symbol: str,
        current_price: float,
        remaining_quantity: Optional[float] = None,
        realized_pnl_usd: Optional[float] = None,
        mode: str = "PAPER",
    ):
        """
        Updates running price, highest price, unrealized PnL, and remaining balance.
        """
        key = f"{mode.upper()}:{symbol.upper()}"
        pos = self._positions.get(key)
        if not pos:
            return

        pos.current_price = current_price
        if current_price > pos.highest_price:
            pos.highest_price = current_price

        if pos.avg_entry_price > 0:
            pos.unrealized_pnl_pct = round(((current_price - pos.avg_entry_price) / pos.avg_entry_price) * 100.0, 2)

        if remaining_quantity is not None:
            pos.remaining_quantity = remaining_quantity

        if realized_pnl_usd is not None:
            pos.realized_pnl_usd += realized_pnl_usd

        pos.updated_at = datetime.now(timezone.utc).isoformat()

    def clear(self):
        """Resets tracking (used for tests and full resets)."""
        self._positions.clear()


# Singleton
position_state_machine = PositionStateMachine()
