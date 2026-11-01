"""
AI Agent Registry for SOFIA MEME BOT V2.
Fulfills PRD Section 4 (AI Agent Organization) & Section 8.1 (Decision Authority).
Manages metadata, health metrics, and lifecycle for all 6 specialized agents.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AgentMetadata(BaseModel):
    id: str
    name: str
    role: str
    description: str
    model: str
    provider: str
    status: str = "active"  # active, degraded, standby
    total_evaluations: int = 0
    total_errors: int = 0
    last_evaluation_iso: Optional[str] = None
    last_decision: Optional[str] = None
    last_score: Optional[float] = None


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {
            "entry_intelligence": AgentMetadata(
                id="entry_intelligence",
                name="Entry Intelligence Agent",
                role="Chief Entry Analyst",
                description="Evaluates candidates on 6 dimensions (Structure, Momentum, Smart Money, Liquidity, Holder, Narrative).",
                model="google/gemini-2.0-flash-exp:free",
                provider="openrouter",
            ),
            "exit_intelligence": AgentMetadata(
                id="exit_intelligence",
                name="Exit Intelligence Agent",
                role="Chief Exit Analyst",
                description="Monitors open positions, recommends partial TP (25/50/75/100%) or full exit based on momentum & liquidity decay.",
                model="google/gemini-2.0-flash-exp:free",
                provider="openrouter",
            ),
            "market_analyst": AgentMetadata(
                id="market_analyst",
                name="Market Analyst Agent",
                role="Macro & Solana Regime Analyst",
                description="Monitors broader Solana conditions, SOL volatility, and meme sector sentiment.",
                model="google/gemini-2.0-flash-exp:free",
                provider="openrouter",
            ),
            "smart_money_analyst": AgentMetadata(
                id="smart_money_analyst",
                name="Smart Money Analyst",
                role="Wallet Intelligence & Cluster Tracker",
                description="Tracks whale accumulation, wallet splitting, and cluster insider behavior.",
                model="google/gemini-2.0-flash-exp:free",
                provider="openrouter",
            ),
            "risk_analyst": AgentMetadata(
                id="risk_analyst",
                name="Risk Analyst Agent",
                role="Chief Risk Officer & Veto Gate",
                description="Audits liquidity, mint/freeze authority, dev concentration, and exercises absolute veto power.",
                model="deterministic_rules",
                provider="deterministic",
            ),
            "trade_supervisor": AgentMetadata(
                id="trade_supervisor",
                name="Trade Supervisor",
                role="Central Autonomous Supervisor",
                description="Coordinates agents, resolves conflicts, enforces trading policy, and verifies quotes before execution.",
                model="deterministic_core",
                provider="deterministic",
            ),
        }

    def get_agent(self, agent_id: str) -> Optional[AgentMetadata]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        return [agent.model_dump() for agent in self._agents.values()]

    def record_decision(self, agent_id: str, decision: str, score: float, is_error: bool = False):
        agent = self._agents.get(agent_id)
        if agent:
            agent.total_evaluations += 1
            if is_error:
                agent.total_errors += 1
            agent.last_decision = decision
            agent.last_score = score
            agent.last_evaluation_iso = datetime.now(timezone.utc).isoformat()

    def update_agent_model(self, agent_id: str, model: str, provider: str):
        agent = self._agents.get(agent_id)
        if agent:
            agent.model = model
            agent.provider = provider


# Global agent registry instance
agent_registry = AgentRegistry()
