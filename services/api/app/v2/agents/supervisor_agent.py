"""
Supervisor Agent for SOFIA MEME BOT V2.
Acts as the Autonomous Trade Supervisor agent interface.
Fulfills PRD Section 4.6 & Section 8.
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.v2.ai.schemas import SupervisorStatusOutput
from app.v2.core.supervisor import trade_supervisor
from app.v2.agents.registry import agent_registry

logger = logging.getLogger("sofia.v2.supervisor_agent")


class SupervisorAgent:
    """
    Autonomous Trade Supervisor Agent:
    Monitors overall agent ecosystem, orchestrates consensus,
    enforces circuit breakers, and reports telemetry.
    """

    AGENT_ID = "trade_supervisor"

    def __init__(self):
        self.metadata = agent_registry.get_agent(self.AGENT_ID)

    def get_status(self, db: Optional[Session] = None) -> SupervisorStatusOutput:
        return trade_supervisor.get_system_status(db=db)

    def trigger_tick(self, db: Session, strategy_mode: str = "DEFAULT", mode: str = "PAPER") -> List[Dict[str, Any]]:
        return trade_supervisor.supervise_positions_tick(db=db, strategy_mode=strategy_mode, mode=mode)

    def engage_emergency_stop(self, reason: str = "OPERATOR_KILL_SWITCH"):
        trade_supervisor.engage_kill_switch(reason=reason)

    def restore_system(self):
        trade_supervisor.disengage_kill_switch()


# Singleton
supervisor_agent = SupervisorAgent()
