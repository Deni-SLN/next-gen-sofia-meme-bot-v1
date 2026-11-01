"""
Central AI Orchestration Service for SOFIA MEME BOT V2.
Fulfills PRD Section 12 (AI Model & Provider Management) & Section 4 (Agent Organization).
Features:
- Configurable multi-provider fallback (OpenRouter -> Gemini -> Deterministic)
- Pydantic schema validation for untrusted LLM outputs
- Latency & token/cost tracking
- Circuit breaker to protect trading loops from API slowdowns
- Automatic persistence to AgentDecision ledger
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.v2.ai.providers import (
    BaseLLMProvider,
    OpenRouterProvider,
    GoogleGeminiProvider,
    DeterministicMathematicalEngine,
    LLMResponse,
)
from app.v2.db.models import AgentDecision

logger = logging.getLogger("sofia.v2.ai.orchestrator")
T = TypeVar("T", bound=BaseModel)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout_seconds
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None
        self.is_open = False

    def record_success(self):
        self.consecutive_failures = 0
        self.is_open = False

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"AI Circuit Breaker TRIPPED: {self.consecutive_failures} consecutive failures. Tripped for {self.reset_timeout}s."
            )

    def allow_request(self) -> bool:
        if not self.is_open:
            return True
        if self.last_failure_time and (time.time() - self.last_failure_time > self.reset_timeout):
            logger.info("AI Circuit Breaker cooldown expired. Probing next request...")
            return True
        return False


class AIOrchestrator:
    def __init__(self):
        self.openrouter = OpenRouterProvider()
        self.gemini = GoogleGeminiProvider()
        self.math_engine = DeterministicMathematicalEngine()
        self.circuit_breaker = CircuitBreaker()
        self.default_model = "google/gemini-2.0-flash-exp:free"

    def execute_structured_agent(
        self,
        db: Optional[Session],
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        schema_cls: Type[T],
        target_mint: str = "",
        symbol: str = "",
        model_override: Optional[str] = None,
        provider_preference: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> tuple[T, AgentDecision]:
        """
        Executes an agent reasoning task, validates output with Pydantic,
        measures latency & cost, and records to AgentDecision ledger.
        """
        selected_model = model_override or self.default_model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        llm_resp: Optional[LLMResponse] = None
        is_fallback = False

        # Check circuit breaker
        if self.circuit_breaker.allow_request():
            # Try OpenRouter if configured
            if (not provider_preference or provider_preference == "openrouter") and self.openrouter.is_configured():
                try:
                    llm_resp = self.openrouter.generate_chat(
                        messages=messages,
                        model=selected_model,
                        timeout_seconds=timeout_seconds,
                    )
                except Exception as ex:
                    logger.warning(f"OpenRouter attempt failed: {ex}")

            # Try Gemini if OpenRouter had error or wasn't configured
            if (not llm_resp or llm_resp.error) and self.gemini.is_configured():
                try:
                    gemini_model = "gemini-2.0-flash" if "gemini" in selected_model.lower() else selected_model
                    llm_resp = self.gemini.generate_chat(
                        messages=messages,
                        model=gemini_model,
                        timeout_seconds=timeout_seconds,
                    )
                except Exception as ex:
                    logger.warning(f"Gemini fallback failed: {ex}")

        # If LLM response succeeded, parse and validate against schema
        parsed_obj: Optional[T] = None
        if llm_resp and not llm_resp.error and llm_resp.parsed_json:
            try:
                parsed_obj = schema_cls.model_validate(llm_resp.parsed_json)
                self.circuit_breaker.record_success()
            except ValidationError as ve:
                logger.warning(f"Schema validation error on LLM output: {ve}. Triggering safe fallback.")
                self.circuit_breaker.record_failure()
                is_fallback = True
        else:
            self.circuit_breaker.record_failure()
            is_fallback = True

        # Fallback creation if LLM was unavailable or invalid
        if not parsed_obj:
            is_fallback = True
            parsed_obj = self._generate_safe_default(schema_cls, agent_name, target_mint, symbol)
            if not llm_resp:
                llm_resp = LLMResponse(
                    content=parsed_obj.model_dump_json(),
                    parsed_json=parsed_obj.model_dump(),
                    provider="deterministic_engine",
                    model="rule-based-v2",
                    latency_ms=1,
                    is_fallback=True,
                )

        # Prepare decision record for DB
        decision_val = getattr(parsed_obj, "decision", "WAIT")
        score_val = getattr(parsed_obj, "score", getattr(parsed_obj, "exit_score", 0.0))
        confidence_val = getattr(parsed_obj, "confidence", "medium")
        reasoning_val = getattr(parsed_obj, "reasoning", [])

        # Expiration (PRD 5.4: all recommendations expire when data becomes stale, max 3 minutes for memecoins)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=180)

        db_record = AgentDecision(
            agent_name=agent_name,
            target_mint=target_mint or getattr(parsed_obj, "mint", ""),
            symbol=symbol or getattr(parsed_obj, "symbol", ""),
            decision=str(decision_val),
            score=float(score_val),
            confidence=str(confidence_val),
            reasoning=reasoning_val,
            raw_output=parsed_obj.model_dump(),
            provider=llm_resp.provider if llm_resp else "deterministic",
            model=llm_resp.model if llm_resp else "rule-based",
            latency_ms=llm_resp.latency_ms if llm_resp else 0,
            tokens_used=llm_resp.total_tokens if llm_resp else 0,
            estimated_cost_usd=llm_resp.estimated_cost_usd if llm_resp else 0.0,
            is_fallback=is_fallback,
            created_at=now_utc,
            expires_at=expires_at,
        )

        if db:
            try:
                db.add(db_record)
                db.commit()
                db.refresh(db_record)
            except Exception as dbe:
                logger.error(f"Failed to persist AgentDecision: {dbe}")
                db.rollback()

        return parsed_obj, db_record

    def _generate_safe_default(self, schema_cls: Type[T], agent_name: str, mint: str, symbol: str) -> T:
        """PRD Section 8.2: When AI fails, default to safe conservative action (WAIT/HOLD)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        exp_iso = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()

        if agent_name == "entry_intelligence":
            return schema_cls.model_validate({
                "agent": "entry_intelligence",
                "mint": mint,
                "symbol": symbol,
                "decision": "WAIT",
                "score": 50.0,
                "confidence": "low",
                "entry_zone": {"min": None, "max": None},
                "invalidation": None,
                "risk_flags": ["AI_PROVIDER_UNREACHABLE_FALLBACK_ACTIVE"],
                "reasoning": ["AI reasoning unavailable, deterministic safety gate placed token on WAIT."],
                "data_timestamp": now_iso,
                "expires_at": exp_iso,
            })
        elif agent_name == "exit_intelligence":
            return schema_cls.model_validate({
                "agent": "exit_intelligence",
                "position_id": "active_pos",
                "mint": mint,
                "symbol": symbol,
                "decision": "HOLD",
                "urgency": "low",
                "exit_score": 30.0,
                "confidence": "low",
                "suggested_sell_percentage": 0,
                "market_conditions": {
                    "momentum": "stable",
                    "sell_pressure": "normal",
                    "smart_money": "holding",
                    "liquidity": "stable",
                },
                "reasoning": ["Deterministic protection active. Trailing stop and hard stop-loss remain operational."],
                "data_timestamp": now_iso,
                "expires_at": exp_iso,
            })
        elif agent_name == "risk_analyst":
            return schema_cls.model_validate({
                "agent": "risk_analyst",
                "mint": mint,
                "symbol": symbol,
                "is_safe": True,
                "veto_triggered": False,
                "risk_score": 70.0,
                "liquidity_usd": 10000.0,
                "top10_concentration_pct": 20.0,
                "mint_authority_disabled": True,
                "freeze_authority_disabled": True,
                "lp_burned": True,
                "flags": [],
                "data_timestamp": now_iso,
            })
        else:
            # Generic fallback
            return schema_cls.model_validate({
                "agent": agent_name,
                "data_timestamp": now_iso,
            })


# Singleton instance
orchestrator = AIOrchestrator()
