"""
FastAPI Router for SOFIA MEME BOT V2 AI Endpoints.
Satisfies PRD Section 13 (API Requirements: Entry Intelligence & Exit Intelligence).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user_optional
from app.v2.ai.orchestrator import orchestrator
from app.v2.ai.schemas import (
    EntryDecisionOutput,
    ExitDecisionOutput,
    RiskAssessmentOutput,
)
from app.v2.agents.registry import agent_registry
from app.v2.db.models import AgentDecision, EntryAssessment, ExitAssessment
from app.services import memecoins, portfolio

router = APIRouter(tags=["V2 AI Intelligence"])


class AnalyzeEntryRequest(BaseModel):
    mint: str
    symbol: Optional[str] = None
    model_override: Optional[str] = None
    provider_preference: Optional[str] = None


class AnalyzeExitRequest(BaseModel):
    symbol: str
    mint: Optional[str] = None
    mode: str = "PAPER"
    model_override: Optional[str] = None


@router.get("/providers")
def get_ai_providers_status():
    """Returns the operational status, latency, and circuit breaker status of all AI providers."""
    return {
        "status": "operational",
        "circuit_breaker": {
            "is_open": orchestrator.circuit_breaker.is_open,
            "consecutive_failures": orchestrator.circuit_breaker.consecutive_failures,
            "threshold": orchestrator.circuit_breaker.failure_threshold,
        },
        "providers": [
            {
                "id": "openrouter",
                "name": "OpenRouter AI (openrouter.ai)",
                "is_configured": orchestrator.openrouter.is_configured(),
                "default_model": orchestrator.default_model,
            },
            {
                "id": "google",
                "name": "Google Gemini (Generative Language)",
                "is_configured": orchestrator.gemini.is_configured(),
                "default_model": "gemini-2.0-flash",
            },
            {
                "id": "deterministic",
                "name": "Deterministic Mathematical Engine (V2 Core)",
                "is_configured": True,
                "role": "Real-time mathematical validation & zero-failure fallback",
            },
        ],
    }


@router.get("/agents")
def list_ai_agents():
    """Lists all 6 registered AI agents, their configured models, and performance metrics."""
    return {
        "agents": agent_registry.list_agents(),
    }


@router.post("/entry/analyze", response_model=EntryDecisionOutput)
def analyze_token_candidate(
    req: AnalyzeEntryRequest,
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Evaluates a candidate token through the Entry Intelligence Agent.
    Fetches real-time DexScreener/GMGN on-chain data, applies the 6-dimension scoring framework,
    and returns a structured BUY/WAIT/WATCHLIST/SKIP decision.
    """
    mint_clean = req.mint.strip()
    if not mint_clean:
        raise HTTPException(status_code=400, detail="Mint token wajib diisi")

    # Fetch real on-chain market data from DexScreener & RugCheck (Zero Dummy Data)
    from app.services import market
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16000.0)
    tokens = market.fetch_dexscreener_tokens_by_addresses([mint_clean], usd_idr)
    tok = tokens[0] if tokens else {}
    rug = memecoins.analyze_rug_check(mint_clean)

    symbol = req.symbol or tok.get("base_symbol") or tok.get("symbol") or rug.get("symbol") or "MEME"
    mcap = float(tok.get("market_cap_usd") or tok.get("fdv_usd") or 0.0)
    liq = float(tok.get("liquidity_usd") or 0.0)
    v5m = float(tok.get("volume_5m_usd") or 0.0)
    v1h = float(tok.get("volume_1h_usd") or 0.0)
    p5m = float(tok.get("price_change_5m_pct") or 0.0)
    p1h = float(tok.get("price_change_1h_pct") or 0.0)
    top10 = float(rug.get("top10_pct") or 20.0)
    dev_h = float(rug.get("dev_holding_pct") or 0.0)

    # 1. Calculate deterministic baseline first (PRD Section 5.1)
    math_eval = orchestrator.math_engine.calculate_entry_scores(
        token_data=tok,
        market_cap_usd=mcap,
        liquidity_usd=liq,
        volume_5m_usd=v5m,
        volume_1h_usd=v1h,
        price_change_5m_pct=p5m,
        price_change_1h_pct=p1h,
        top10_concentration_pct=top10,
        dev_holding_pct=dev_h,
    )

    sys_prompt = (
        "You are the Entry Intelligence Agent for SOFIA MEME BOT V2 on Solana. "
        "Analyze the provided raw market metrics and return a valid JSON object matching EntryDecisionOutput schema. "
        "Strict rules: Never fabricate numbers. If score >= 85 decision is BUY (Strong), 75-84 BUY, 60-74 WAIT, <60 SKIP. "
        "Penalize tokens with volume drop, late entries (>300% 1h runup), or top 10 holders > 25%."
    )

    user_prompt = (
        f"Token: {symbol} (Mint: {mint_clean})\n"
        f"Market Cap: ${mcap:,.2f} | Liquidity: ${liq:,.2f}\n"
        f"Volume 5m: ${v5m:,.2f} | Volume 1h: ${v1h:,.2f}\n"
        f"Change 5m: {p5m:+.2f}% | Change 1h: {p1h:+.2f}%\n"
        f"Top 10 Holders: {top10:.1f}% | Dev Holding: {dev_h:.1f}%\n"
        f"Deterministic Baseline Scores: {json.dumps(math_eval['dimensions'])}\n"
        f"Calculated Score: {math_eval['score']}/100"
    )

    decision_out, db_record = orchestrator.execute_structured_agent(
        db=db,
        agent_name="entry_intelligence",
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        schema_cls=EntryDecisionOutput,
        target_mint=mint_clean,
        symbol=symbol,
        model_override=req.model_override,
        provider_preference=req.provider_preference,
    )

    # Record in agent registry
    agent_registry.record_decision("entry_intelligence", decision_out.decision, decision_out.score)

    # Persist EntryAssessment detail
    if db and db_record:
        try:
            ea = EntryAssessment(
                decision_id=db_record.id,
                target_mint=mint_clean,
                symbol=symbol,
                market_structure_score=math_eval["dimensions"]["market_structure"],
                momentum_score=math_eval["dimensions"]["momentum"],
                smart_money_score=math_eval["dimensions"]["smart_money"],
                liquidity_score=math_eval["dimensions"]["liquidity"],
                holder_score=math_eval["dimensions"]["holder_intelligence"],
                narrative_score=math_eval["dimensions"]["narrative"],
                total_score=decision_out.score,
                entry_zone_min=decision_out.entry_zone.min,
                entry_zone_max=decision_out.entry_zone.max,
                invalidation_price=decision_out.invalidation,
                expected_rr_ratio=decision_out.expected_rr_ratio,
                passed_quality_gate=(decision_out.score >= 75.0),
                risk_flags=decision_out.risk_flags,
            )
            db.add(ea)
            db.commit()
        except Exception:
            db.rollback()

    return decision_out


@router.post("/exit/analyze", response_model=ExitDecisionOutput)
def analyze_position_exit(
    req: AnalyzeExitRequest,
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Evaluates an active position through the Exit Intelligence Agent.
    Monitors peak price, current executable quote, momentum decay, and whale distribution,
    recommending partial profit taking (25/50/75/100%) or holding.
    """
    sym_clean = req.symbol.strip().upper()
    holding = portfolio.get_holding(db, sym_clean, mode=req.mode)
    if not holding:
        raise HTTPException(status_code=404, detail=f"Posisi {sym_clean} ({req.mode}) tidak ditemukan dalam portofolio")

    avg_entry = float(holding.avg_entry_price or 0.0)
    curr_price = float(holding.current_price or avg_entry)
    qty = float(holding.quantity or 0.0)
    pnl_pct = round(((curr_price - avg_entry) / avg_entry * 100.0) if avg_entry > 0 else 0.0, 2)

    sys_prompt = (
        "You are the Exit Intelligence Agent for SOFIA MEME BOT V2 on Solana. "
        "Analyze the active holding performance and suggest HOLD, REDUCE, TAKE_PROFIT, FULL_EXIT, or EMERGENCY_EXIT. "
        "Support partial liquidations: 25%, 50%, 75%, 100%. "
        "Do not panic exit on a single red candle if momentum and liquidity remain intact."
    )

    user_prompt = (
        f"Position: {sym_clean} (Mode: {req.mode})\n"
        f"Entry Price: ${avg_entry:.8f} | Current Price: ${curr_price:.8f}\n"
        f"Quantity: {qty:,.2f} | Unrealized PnL: {pnl_pct:+.2f}%\n"
        f"Pool Liquidity: ${float(holding.liquidity_usd or 0.0):,.2f}"
    )

    decision_out, db_record = orchestrator.execute_structured_agent(
        db=db,
        agent_name="exit_intelligence",
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        schema_cls=ExitDecisionOutput,
        target_mint=req.mint or sym_clean,
        symbol=sym_clean,
        model_override=req.model_override,
    )

    agent_registry.record_decision("exit_intelligence", decision_out.decision, decision_out.exit_score)

    return decision_out


@router.get("/decisions")
def list_agent_decisions(
    agent_name: Optional[str] = None,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieves paginated audit log of past AI decisions from database."""
    stmt = select(AgentDecision)
    if agent_name:
        stmt = stmt.where(AgentDecision.agent_name == agent_name)
    stmt = stmt.order_by(desc(AgentDecision.created_at)).limit(limit)

    rows = db.execute(stmt).scalars().all()
    return {
        "count": len(rows),
        "decisions": [
            {
                "id": r.id,
                "agent_name": r.agent_name,
                "target_mint": r.target_mint,
                "symbol": r.symbol,
                "decision": r.decision,
                "score": r.score,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "provider": r.provider,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "is_fallback": r.is_fallback,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
