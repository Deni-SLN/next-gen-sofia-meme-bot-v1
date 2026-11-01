"""
Pydantic Schemas for SOFIA MEME BOT V2 AI Agents and Structured Outputs.
Strictly adheres to PRD Section 4 (AI Agent Organization) & Section 5/6 (Entry/Exit Intelligence).
All numbers are verified against actual market data.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class EntryZone(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None


class EntryDimensionsScore(BaseModel):
    market_structure: float = Field(default=0.0, ge=0.0, le=20.0, description="Max weight 20")
    momentum: float = Field(default=0.0, ge=0.0, le=20.0, description="Max weight 20")
    smart_money: float = Field(default=0.0, ge=0.0, le=20.0, description="Max weight 20")
    liquidity: float = Field(default=0.0, ge=0.0, le=15.0, description="Max weight 15")
    holder_intelligence: float = Field(default=0.0, ge=0.0, le=15.0, description="Max weight 15")
    narrative: float = Field(default=0.0, ge=0.0, le=10.0, description="Max weight 10")

    @property
    def total_score(self) -> float:
        return round(
            self.market_structure
            + self.momentum
            + self.smart_money
            + self.liquidity
            + self.holder_intelligence
            + self.narrative,
            1,
        )


class EntryDecisionOutput(BaseModel):
    agent: Literal["entry_intelligence"] = "entry_intelligence"
    mint: str
    symbol: str
    decision: Literal["BUY", "WAIT", "WATCHLIST", "SKIP"]
    score: float = Field(ge=0.0, le=100.0)
    confidence: Literal["low", "medium", "high"]
    entry_zone: EntryZone = Field(default_factory=EntryZone)
    invalidation: Optional[float] = None
    expected_rr_ratio: Optional[float] = None
    dimensions: Optional[EntryDimensionsScore] = None
    risk_flags: List[str] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)
    data_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str


class ExitMarketConditions(BaseModel):
    momentum: Literal["strengthening", "stable", "weakening", "collapsed"] = "stable"
    sell_pressure: Literal["low", "normal", "increasing", "dominant"] = "normal"
    smart_money: Literal["accumulation", "holding", "distribution", "dumping"] = "holding"
    liquidity: Literal["deep", "stable", "decaying", "critical_drop"] = "stable"


class ExitDecisionOutput(BaseModel):
    agent: Literal["exit_intelligence"] = "exit_intelligence"
    position_id: str
    mint: str
    symbol: str
    decision: Literal["HOLD", "WAIT", "TIGHTEN_STOP", "REDUCE", "TAKE_PROFIT", "FULL_EXIT", "EMERGENCY_EXIT"]
    urgency: Literal["low", "medium", "high", "critical"]
    exit_score: float = Field(ge=0.0, le=100.0, description="Urgency score 0-100")
    confidence: Literal["low", "medium", "high"]
    suggested_sell_percentage: int = Field(default=0, ge=0, le=100, description="0, 25, 50, 75, 100")
    market_conditions: ExitMarketConditions = Field(default_factory=ExitMarketConditions)
    reasoning: List[str] = Field(default_factory=list)
    highest_price_observed: Optional[float] = None
    current_executable_price: Optional[float] = None
    data_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str


class RiskAssessmentOutput(BaseModel):
    agent: Literal["risk_analyst"] = "risk_analyst"
    mint: str
    symbol: str
    is_safe: bool
    veto_triggered: bool
    veto_reason: Optional[str] = None
    risk_score: float = Field(ge=0.0, le=100.0, description="100=safest, 0=extreme risk")
    liquidity_usd: float
    top10_concentration_pct: float
    mint_authority_disabled: bool
    freeze_authority_disabled: bool
    lp_burned: bool
    flags: List[str] = Field(default_factory=list)
    data_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SmartMoneyInsight(BaseModel):
    agent: Literal["smart_money_analyst"] = "smart_money_analyst"
    mint: str
    symbol: str
    accumulating_wallets_count: int = 0
    distributing_wallets_count: int = 0
    net_smart_inflow_sol: float = 0.0
    coordinated_cluster_detected: bool = False
    insider_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    summary: str
    data_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MarketRegimeOutput(BaseModel):
    agent: Literal["market_analyst"] = "market_analyst"
    regime: Literal["RISK_ON", "RISK_OFF", "CHOPPY", "EXTREME_VOLATILITY"]
    sol_price_usd: float
    sol_trend_1h: Literal["bullish", "neutral", "bearish"]
    meme_sector_sentiment: Literal["euphoric", "bullish", "neutral", "bearish", "capitulation"]
    trading_allowed: bool
    max_open_positions_allowed: int = 3
    suggested_risk_per_trade_sol: float = 0.05
    reasoning: List[str] = Field(default_factory=list)
    data_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SupervisorStatusOutput(BaseModel):
    agent: Literal["trade_supervisor"] = "trade_supervisor"
    system_status: Literal["operational", "degraded", "halted"]
    ai_service_online: bool
    deterministic_risk_online: bool
    active_positions_count: int
    daily_realized_pnl_usd: float
    kill_switch_engaged: bool
    circuit_breaker_active: bool
    registered_agents: List[Dict[str, Any]]
    last_reconciled_at: Optional[str] = None
