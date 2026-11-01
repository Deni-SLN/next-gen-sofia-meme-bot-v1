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

from app.v2.services.entry_intelligence import entry_intelligence
from app.v2.core.quality_gate import quality_gate
from app.v2.services.scanner_bridge import scanner_bridge
from app.v2.services.paper_executor import paper_executor

router = APIRouter(tags=["V2 AI Intelligence"])


class AnalyzeEntryRequest(BaseModel):
    mint: str
    symbol: Optional[str] = None
    strategy_mode: str = "DEFAULT"
    model_override: Optional[str] = None
    provider_preference: Optional[str] = None
    force_deterministic: bool = False


class SimulatePaperRequest(BaseModel):
    mint: str
    symbol: Optional[str] = None
    strategy_mode: str = "DEFAULT"
    allocation_usd: float = 1.0


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


@router.get("/entry/candidates")
def list_evaluated_candidates(
    strategy_mode: str = Query(default="DEFAULT", description="DEFAULT, SAFE, or AGGRESSIVE"),
    limit: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    """
    Scans live Solana meme pools from DexScreener & GMGN radar,
    evaluates candidates across the 6-dimension Entry Intelligence framework,
    and runs them through the Trade Quality Gate with deterministic risk vetoes.
    """
    return {
        "strategy_mode": strategy_mode.upper(),
        "limit": limit,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": scanner_bridge.scan_and_evaluate_candidates(
            db=db,
            strategy_mode=strategy_mode,
            limit=limit,
            force_deterministic=True,
        ),
    }


@router.post("/entry/analyze", response_model=EntryDecisionOutput)
def analyze_token_candidate(
    req: AnalyzeEntryRequest,
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Evaluates a candidate token through the Entry Intelligence Agent and Trade Quality Gate.
    Calculates 6 analytical dimensions, verifies data freshness (<180s), and creates an immutable snapshot.
    """
    mint_clean = req.mint.strip()
    if not mint_clean:
        raise HTTPException(status_code=400, detail="Mint token wajib diisi")

    # Fetch real on-chain market data from DexScreener & RugCheck
    from app.services import market
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16000.0)
    tokens = market.fetch_dexscreener_tokens_by_addresses([mint_clean], usd_idr)
    tok = tokens[0] if tokens else {}
    rug = memecoins.analyze_rug_check(mint_clean)

    merged = {
        **tok,
        "contract": mint_clean,
        "symbol": req.symbol or tok.get("base_symbol") or tok.get("symbol") or rug.get("symbol") or "MEME",
        "top10_concentration_pct": rug.get("top10_pct", 20.0),
        "dev_holding_pct": rug.get("dev_holding_pct", 0.0),
        "mint_revoked": rug.get("mint_revoked", False),
        "freeze_revoked": rug.get("freeze_revoked", False),
        "lp_burned": rug.get("lp_burned", False),
        "honeypot": rug.get("honeypot", False),
        "data_timestamp": tok.get("data_timestamp") or tok.get("updated_at"),
    }

    # Evaluate via independent Entry Intelligence Service
    decision_out, snapshot = entry_intelligence.evaluate_candidate(
        token_data=merged,
        db=db,
        model_override=req.model_override,
        provider_preference=req.provider_preference,
        force_deterministic=req.force_deterministic,
    )

    # Evaluate via Trade Quality Gate (Deterministic Risk Veto)
    qg_res = quality_gate.evaluate(
        entry_decision=decision_out,
        risk_data=merged,
        strategy_mode=req.strategy_mode,
        db=db,
    )

    return decision_out


@router.post("/entry/simulate-paper")
def simulate_paper_entry(
    req: SimulatePaperRequest,
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Simulates paper trade execution for an approved candidate token.
    Enforces Directive Item 5: Zero modifications to LIVE trading execution.
    """
    mint_clean = req.mint.strip()
    if not mint_clean:
        raise HTTPException(status_code=400, detail="Mint token wajib diisi")

    from app.services import market
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16000.0)
    tokens = market.fetch_dexscreener_tokens_by_addresses([mint_clean], usd_idr)
    tok = tokens[0] if tokens else {}
    rug = memecoins.analyze_rug_check(mint_clean)

    merged = {
        **tok,
        "contract": mint_clean,
        "symbol": req.symbol or tok.get("base_symbol") or tok.get("symbol") or rug.get("symbol") or "MEME",
        "top10_concentration_pct": rug.get("top10_pct", 20.0),
        "dev_holding_pct": rug.get("dev_holding_pct", 0.0),
        "mint_revoked": rug.get("mint_revoked", False),
        "freeze_revoked": rug.get("freeze_revoked", False),
        "lp_burned": rug.get("lp_burned", False),
        "honeypot": rug.get("honeypot", False),
        "data_timestamp": tok.get("data_timestamp") or tok.get("updated_at"),
    }

    decision_out, _ = entry_intelligence.evaluate_candidate(
        token_data=merged,
        db=db,
        force_deterministic=True,
    )

    qg_res = quality_gate.evaluate(
        entry_decision=decision_out,
        risk_data=merged,
        strategy_mode=req.strategy_mode,
        db=db,
    )

    if not qg_res.passed:
        raise HTTPException(
            status_code=400,
            detail=f"Trade Quality Gate DITOLAK: {qg_res.verdict}. Alasan: {'; '.join(qg_res.rejection_reasons)}",
        )

    result = paper_executor.execute_paper_entry(
        db=db,
        entry_decision=decision_out,
        quality_gate_result=qg_res,
        allocation_usd=req.allocation_usd,
    )

    return result

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
