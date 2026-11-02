"""
Autonomous Trade Supervisor for SOFIA MEME BOT V2.
Coordinates Entry/Exit intelligence, manages position lifecycles,
resolves inter-agent conflicts, and enforces global risk invariants.
Strictly adheres to:
- PRD Section 4.6 (Trade Supervisor Agent)
- PRD Section 7 (Position Manager)
- PRD Section 8 (Trade Supervisor & Conflict Resolution)
- PRD Section 18 Phase 4 Deliverables
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.models import PortfolioHolding, Trade
from app.v2.ai.schemas import SupervisorStatusOutput, ConflictResolutionOutput
from app.v2.agents.registry import agent_registry
from app.v2.core.position_state_machine import position_state_machine
from app.v2.core.conflict_resolver import conflict_resolver
from app.v2.core.exit_policy import exit_policy
from app.v2.services.exit_intelligence import exit_intelligence
from app.v2.services.partial_exit_manager import partial_exit_manager
from app.v2.services.adaptive_profit_manager import adaptive_profit_manager

logger = logging.getLogger("sofia.v2.supervisor")


class AutonomousTradeSupervisor:
    """
    Central Autonomous Supervisor:
    Coordinates all specialized agents, monitors position states, arbitrates conflicts,
    and manages automated recovery.
    """

    MAX_CONSECUTIVE_ERRORS_CIRCUIT_BREAKER = 5
    DEFAULT_DAILY_DRAWDOWN_LIMIT_USD = 50.0  # Conservative circuit breaker for testing/paper

    def __init__(self):
        self._kill_switch_engaged: bool = False
        self._circuit_breaker_active: bool = False
        self._consecutive_errors: int = 0
        self._last_reconciled_at: Optional[str] = None
        self._initialized: bool = False

    def engage_kill_switch(self, reason: str = "MANUAL_OPERATOR_OVERRIDE"):
        """Immediately halts all automated trading activities."""
        self._kill_switch_engaged = True
        logger.warning(f"[SUPERVISOR] EMERGENCY KILL SWITCH ENGAGED! Reason: {reason}")

    def disengage_kill_switch(self):
        """Disengages manual kill switch."""
        self._kill_switch_engaged = False
        self._consecutive_errors = 0
        self._circuit_breaker_active = False
        logger.info("[SUPERVISOR] Kill switch disengaged. System restored to operational.")

    def reset_circuit_breaker(self):
        """Resets automatic circuit breaker after investigation."""
        self._circuit_breaker_active = False
        self._consecutive_errors = 0
        logger.info("[SUPERVISOR] Circuit breaker reset.")

    def record_agent_error(self, agent_name: str, error_msg: str):
        """Tracks agent failures and trips circuit breaker if threshold exceeded."""
        self._consecutive_errors += 1
        agent_registry.record_decision(agent_name, "ERROR", 0.0, is_error=True)
        logger.error(f"[SUPERVISOR] Error in agent '{agent_name}' ({self._consecutive_errors}/{self.MAX_CONSECUTIVE_ERRORS_CIRCUIT_BREAKER}): {error_msg}")

        if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS_CIRCUIT_BREAKER:
            self._circuit_breaker_active = True
            logger.critical(
                f"[SUPERVISOR CIRCUIT BREAKER] Tripped after {self._consecutive_errors} consecutive errors! Halting new entries."
            )

    def record_success(self):
        """Resets consecutive error counter on successful action."""
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0

    def get_system_status(self, db: Optional[Session] = None) -> SupervisorStatusOutput:
        """
        Gathers comprehensive telemetry across all registered agents and active holdings.
        """
        active_pos_count = 0
        daily_pnl_usd = 0.0

        if db:
            try:
                # Count open holdings
                q_holdings = select(func.count(PortfolioHolding.id)).where(PortfolioHolding.quantity > 0)
                active_pos_count = db.execute(q_holdings).scalar_one() or 0

                # Compute today's realized PnL
                now_utc = datetime.now(timezone.utc)
                start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
                q_pnl = select(func.sum(Trade.pnl)).where(
                    Trade.side == "sell",
                    Trade.status == "closed",
                    Trade.closed_at >= start_of_day,
                )
                daily_pnl_usd = float(db.execute(q_pnl).scalar_one() or 0.0)
            except Exception as e:
                logger.error(f"Error gathering DB telemetry for supervisor: {e}")

        # Determine overall system status
        if self._kill_switch_engaged:
            sys_status = "halted"
        elif self._circuit_breaker_active:
            sys_status = "degraded"
        else:
            sys_status = "operational"

        return SupervisorStatusOutput(
            agent="trade_supervisor",
            system_status=sys_status,
            ai_service_online=not self._circuit_breaker_active,
            deterministic_risk_online=True,
            active_positions_count=active_pos_count,
            daily_realized_pnl_usd=round(daily_pnl_usd, 4),
            kill_switch_engaged=self._kill_switch_engaged,
            circuit_breaker_active=self._circuit_breaker_active,
            registered_agents=agent_registry.list_agents(),
            last_reconciled_at=self._last_reconciled_at,
        )

    def recover_positions_after_restart(self, db: Session, mode: str = "PAPER"):
        """
        Recovers active positions after server reboot or reload:
        - Syncs existing holdings into PositionStateMachine
        - Reconstructs peak prices and trailing stop states
        Fulfills PRD Section 7.3 & Acceptance Criterion 11.
        """
        trade_mode = mode.upper()
        holdings = db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.mode == trade_mode,
                PortfolioHolding.quantity > 0,
            )
        ).scalars().all()

        recovered_count = 0
        for h in holdings:
            sym = h.symbol.upper()
            qty = float(h.quantity or 0.0)
            entry_p = float(h.avg_entry_price or 0.0)
            curr_p = float(h.current_price or entry_p)

            # Reconstruct in state machine
            pos = position_state_machine.get_or_create_position(
                symbol=sym,
                mint=getattr(h, "contract", None) or sym,
                mode=trade_mode,
                position_id=str(h.id),
                initial_quantity=qty,
                entry_price=entry_p,
                initial_state="POSITION_OPEN",
            )
            # Transition to MONITORING
            if pos.current_state != "MONITORING":
                try:
                    position_state_machine.transition_to(
                        symbol=sym,
                        new_state="MONITORING",
                        reason="RESTART_RECOVERY",
                        mode=trade_mode,
                    )
                except Exception:
                    pass

            # Reconstruct Adaptive Profit Manager tracking
            adaptive_profit_manager.update_position_tracking(
                symbol=sym,
                current_price=curr_p,
                entry_price=entry_p,
            )
            recovered_count += 1

        self._last_reconciled_at = datetime.now(timezone.utc).isoformat()
        self._initialized = True
        logger.info(f"[SUPERVISOR] Successfully recovered {recovered_count} active {trade_mode} positions into state machine.")
        return recovered_count

    def supervise_positions_tick(
        self,
        db: Session,
        strategy_mode: str = "DEFAULT",
        mode: str = "PAPER",
    ) -> List[Dict[str, Any]]:
        """
        Autonomous monitoring loop tick:
        Inspects all open positions, updates excursion prices, runs exit evaluation,
        resolves conflicts, and executes liquidations if warranted.
        """
        if self._kill_switch_engaged:
            logger.info("[SUPERVISOR TICK] Skipped: Kill switch engaged.")
            return []

        trade_mode = mode.upper()
        holdings = list(
            db.execute(
                select(PortfolioHolding).where(
                    PortfolioHolding.mode == trade_mode,
                    PortfolioHolding.quantity > 0,
                )
            ).scalars().all()
        )

        results = []
        for h in holdings:
            sym = h.symbol.upper()
            try:
                # 1. Ensure position is registered in State Machine
                pos_info = position_state_machine.get_or_create_position(
                    symbol=sym,
                    mint=getattr(h, "contract", None) or sym,
                    mode=trade_mode,
                    position_id=str(h.id),
                    initial_quantity=float(h.quantity or 0.0),
                    entry_price=float(h.avg_entry_price or 0.0),
                    initial_state="MONITORING",
                )

                # 2. Evaluate exit condition
                from app.services import market
                tok_info = market.resolve_holding_live_price(
                    sym,
                    avg_entry_price=float(h.avg_entry_price or 0.0),
                    current_price=float(h.current_price or 0.0),
                ) or {}
                curr_price = float(tok_info.get("price") or h.current_price or h.avg_entry_price)

                pos_data = {
                    "position_id": str(h.id),
                    "symbol": sym,
                    "mint": (tok_info.get("contract") if tok_info else "") or sym,
                    "avg_entry_price": float(h.avg_entry_price or 0.0),
                    "current_price": curr_price,
                    "quantity": float(h.quantity or 0.0),
                    "liquidity_usd": float(h.liquidity_usd or (tok_info.get("liquidity") if tok_info else 25000.0) or 25000.0),
                }

                market_data = {
                    "price": curr_price,
                    "liquidity_usd": float((tok_info.get("liquidity") if tok_info else 0.0) or h.liquidity_usd or 25000.0),
                    "price_change_5m_pct": float(tok_info.get("price_change_5m") or 0.0) if tok_info else 0.0,
                    "price_change_1h_pct": float(tok_info.get("price_change_1h") or 0.0) if tok_info else 0.0,
                    "volume_5m_usd": float(tok_info.get("volume_5m") or 0.0) if tok_info else 0.0,
                    "txns": tok_info.get("txns") if tok_info else {},
                }

                exit_dec, _ = exit_intelligence.evaluate_position(
                    position_data=pos_data,
                    market_data=market_data,
                    db=db,
                    strategy_mode=strategy_mode,
                    force_deterministic=True,
                )

                # 3. Conflict Resolution
                conflict_res = conflict_resolver.resolve_exit_conflict(
                    exit_decision=exit_dec.decision,
                    policy_action=exit_dec.decision,
                    policy_override="RISK VETO" in " ".join(exit_dec.reasoning),
                    policy_reason="; ".join(exit_dec.reasoning),
                    ai_provider_available=not self._circuit_breaker_active,
                )

                # 4. Action Execution if liquidation recommended
                action_taken = "HOLD"
                if exit_dec.suggested_sell_percentage > 0 and exit_dec.decision in ("REDUCE", "TAKE_PROFIT", "FULL_EXIT", "EMERGENCY_EXIT"):
                    # Transition to SELL_PENDING
                    position_state_machine.transition_to(
                        symbol=sym,
                        new_state="SELL_PENDING",
                        reason=f"TRIGGER_{exit_dec.decision}",
                        mode=trade_mode,
                    )

                    # Execute order
                    sell_res = partial_exit_manager.execute_partial_exit(
                        db=db,
                        symbol=sym,
                        sell_pct=exit_dec.suggested_sell_percentage,
                        exit_reason=f"[{strategy_mode}] {exit_dec.decision}: {'; '.join(exit_dec.reasoning[:2])}",
                        mode=trade_mode,
                        exit_score=exit_dec.exit_score,
                    )

                    # Transition to RECONCILIATION
                    position_state_machine.transition_to(
                        symbol=sym,
                        new_state="RECONCILIATION",
                        reason="POST_TRADE_RECONCILIATION",
                        mode=trade_mode,
                    )

                    # If fully closed, finalize to CLOSED; otherwise back to MONITORING
                    if sell_res.get("is_fully_closed"):
                        position_state_machine.transition_to(
                            symbol=sym,
                            new_state="CLOSED",
                            reason="FULL_LIQUIDATION_COMPLETE",
                            mode=trade_mode,
                        )
                    else:
                        position_state_machine.transition_to(
                            symbol=sym,
                            new_state="MONITORING",
                            reason="PARTIAL_EXIT_REMAINDER_ACTIVE",
                            mode=trade_mode,
                        )

                    action_taken = f"SOLD_{exit_dec.suggested_sell_percentage}%"

                results.append({
                    "symbol": sym,
                    "decision": exit_dec.decision,
                    "action_taken": action_taken,
                    "score": exit_dec.exit_score,
                    "conflict_resolution": conflict_res.resolution,
                })
                self.record_success()

            except Exception as ex:
                self.record_agent_error("trade_supervisor", f"Error supervising {sym}: {ex}")
                results.append({
                    "symbol": sym,
                    "decision": "ERROR",
                    "action_taken": "NONE",
                    "error": str(ex),
                })

        self._last_reconciled_at = datetime.now(timezone.utc).isoformat()
        return results


# Singleton
trade_supervisor = AutonomousTradeSupervisor()
