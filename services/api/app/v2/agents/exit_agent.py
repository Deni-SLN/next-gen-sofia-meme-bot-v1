"""
Exit Agent for SOFIA MEME BOT V2.
Encapsulates Exit Intelligence Agent operations and interacts with the Agent Registry.
Fulfills PRD Section 4.2 & Directive Section 3.
"""

import logging
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.v2.ai.schemas import ExitDecisionOutput
from app.v2.services.exit_intelligence import exit_intelligence
from app.v2.services.partial_exit_manager import partial_exit_manager
from app.v2.agents.registry import agent_registry

logger = logging.getLogger("sofia.v2.exit_agent")


class ExitAgent:
    """
    Chief Exit Analyst Agent:
    Monitors active positions, diagnoses market condition decay,
    and coordinates partial or full exit recommendations.
    """

    AGENT_ID = "exit_intelligence"

    def __init__(self):
        self.metadata = agent_registry.get_agent(self.AGENT_ID)

    def evaluate_position(
        self,
        position_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        strategy_mode: str = "DEFAULT",
        force_deterministic: bool = True,
    ) -> Tuple[ExitDecisionOutput, Dict[str, Any]]:
        """
        Evaluates position and returns structured exit recommendation.
        """
        return exit_intelligence.evaluate_position(
            position_data=position_data,
            market_data=market_data,
            db=db,
            strategy_mode=strategy_mode,
            force_deterministic=force_deterministic,
        )

    def execute_exit(
        self,
        db: Session,
        symbol: str,
        sell_pct: float,
        exit_reason: str = "AI_RECOMMENDED_EXIT",
        mode: str = "PAPER",
        exit_decision_id: Optional[int] = None,
        exit_score: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executes a partial or full exit order with balance reconciliation and event recording.
        """
        return partial_exit_manager.execute_partial_exit(
            db=db,
            symbol=symbol,
            sell_pct=sell_pct,
            exit_reason=exit_reason,
            mode=mode,
            exit_decision_id=exit_decision_id,
            exit_score=exit_score,
        )


# Singleton
exit_agent = ExitAgent()
