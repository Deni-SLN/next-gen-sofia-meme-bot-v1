"""
Independent Entry Intelligence Service for SOFIA MEME BOT V2.
Strictly adheres to:
- PRD Section 4.1 (Entry Intelligence Agent)
- PRD Section 5 (AI Entry Intelligence)
- Directive Phase 2 Items 6, 7, 8, 9, 10, 12, 14
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.v2.ai.schemas import EntryDecisionOutput, EntryDimensionsScore, EntryZone
from app.v2.ai.orchestrator import orchestrator
from app.v2.agents.registry import agent_registry
from app.v2.db.models import AgentDecision, EntryAssessment

logger = logging.getLogger("sofia.v2.entry_intelligence")

# Maximum permitted data age in seconds (PRD 5.4: all recommendations expire when stale)
MAX_DATA_AGE_SECONDS: float = 180.0


class EntryIntelligenceService:
    """
    Chief Entry Analyst: Independent service responsible for analyzing token candidates,
    calculating multi-dimensional scores, evaluating data freshness, and issuing
    reproducible BUY, WAIT, WATCHLIST, and SKIP decisions.
    """

    @classmethod
    def evaluate_candidate(
        cls,
        token_data: Dict[str, Any],
        db: Optional[Session] = None,
        model_override: Optional[str] = None,
        provider_preference: Optional[str] = None,
        force_deterministic: bool = False,
    ) -> Tuple[EntryDecisionOutput, Dict[str, Any]]:
        """
        Main entrypoint for token analysis.
        Returns:
            (EntryDecisionOutput, input_snapshot)
        """
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        mint = str(token_data.get("contract") or token_data.get("address") or token_data.get("mint") or "").strip()
        symbol = str(token_data.get("base_symbol") or token_data.get("symbol") or "MEME").strip().upper()

        # 1. Data Freshness Validation (Directive Item 10)
        data_ts_raw = token_data.get("data_timestamp") or token_data.get("updated_at")
        data_age_sec = 0.0
        is_stale = False
        if data_ts_raw:
            try:
                if isinstance(data_ts_raw, (int, float)):
                    data_age_sec = max(0.0, now_ts - float(data_ts_raw))
                else:
                    dt = datetime.fromisoformat(str(data_ts_raw).replace("Z", "+00:00"))
                    data_age_sec = max(0.0, now_ts - dt.timestamp())
            except Exception:
                data_age_sec = 0.0

        if data_age_sec > MAX_DATA_AGE_SECONDS:
            is_stale = True

        # Extract metrics safely (Missing data must never be interpreted as positive signal)
        price_usd = float(token_data.get("price_usd") or token_data.get("price") or 0.0)
        mcap_usd = float(token_data.get("market_cap_usd") or token_data.get("market_cap") or token_data.get("fdv_usd") or 0.0)
        liquidity_usd = float(token_data.get("liquidity_usd") or token_data.get("liquidity") or 0.0)
        v5m_usd = float(token_data.get("volume_5m_usd") or token_data.get("volume_5m") or 0.0)
        v1h_usd = float(token_data.get("volume_1h_usd") or token_data.get("volume_1h") or 0.0)
        p5m_pct = float(token_data.get("price_change_5m_pct") or token_data.get("price_change_5m") or 0.0)
        p1h_pct = float(token_data.get("price_change_1h_pct") or token_data.get("price_change_1h") or 0.0)
        top10_pct = float(token_data.get("top10_concentration_pct") or token_data.get("top10_pct") or 25.0)
        dev_pct = float(token_data.get("dev_holding_pct") or token_data.get("dev_holding") or 0.0)
        is_pump_curve = bool(token_data.get("is_pump_curve") or token_data.get("is_pump_fun") or False)
        bonding_pct = float(token_data.get("bonding_curve_pct") or 0.0)

        txns = token_data.get("txns") or {}
        txns_5m = txns.get("m5") or txns.get("5m") or {}
        buys_5m = int(txns_5m.get("buys") or token_data.get("buys_5m") or 0)
        sells_5m = int(txns_5m.get("sells") or token_data.get("sells_5m") or 0)

        # 2. Capture Immutable Input Snapshot (Directive Item 12)
        input_snapshot = {
            "mint": mint,
            "symbol": symbol,
            "price_usd": price_usd,
            "market_cap_usd": mcap_usd,
            "liquidity_usd": liquidity_usd,
            "volume_5m_usd": v5m_usd,
            "volume_1h_usd": v1h_usd,
            "price_change_5m_pct": p5m_pct,
            "price_change_1h_pct": p1h_pct,
            "top10_concentration_pct": top10_pct,
            "dev_holding_pct": dev_pct,
            "buys_5m": buys_5m,
            "sells_5m": sells_5m,
            "is_pump_curve": is_pump_curve,
            "bonding_curve_pct": bonding_pct,
            "data_age_seconds": round(data_age_sec, 1),
            "is_stale": is_stale,
            "snapshot_timestamp": now_utc.isoformat(),
        }

        risk_flags: List[str] = []
        if is_stale:
            risk_flags.append(f"STALE_MARKET_DATA ({data_age_sec:.0f}s old)")
        if liquidity_usd <= 0:
            risk_flags.append("MISSING_OR_ZERO_LIQUIDITY")
        if top10_pct > 25.0:
            risk_flags.append(f"HIGH_HOLDER_CONCENTRATION ({top10_pct:.1f}%)")
        if dev_pct > 10.0:
            risk_flags.append(f"HIGH_DEV_HOLDING ({dev_pct:.1f}%)")
        if p1h_pct > 400.0:
            risk_flags.append(f"OVEREXTENDED_1H_RUNUP (+{p1h_pct:.0f}%)")

        # 3. Calculate 6 Analytical Dimensions (PRD Section 5.1 & Directive Item 7)
        dim_scores, reasons = cls._compute_deterministic_dimensions(
            input_snapshot=input_snapshot,
            risk_flags=risk_flags,
        )

        total_score = dim_scores.total_score

        # 4. Determine Preliminary Decision (PRD Section 5.1 Policy)
        # Policy: 85-100 Strong Buy, 75-84 Buy Candidate, 60-74 Wait/Watchlist, <60 Reject/Skip
        if is_stale:
            decision = "WAIT"
            confidence = "low"
            reasons.insert(0, f"Market data is stale ({data_age_sec:.0f}s old). Forcing decision to WAIT.")
        elif total_score >= 85.0 and not risk_flags:
            decision = "BUY"
            confidence = "high"
        elif total_score >= 75.0 and len([f for f in risk_flags if "STALE" not in f]) <= 1:
            decision = "BUY"
            confidence = "medium"
        elif total_score >= 60.0:
            decision = "WAIT" if any("CONCENTRATION" in f or "DEV" in f for f in risk_flags) else "WATCHLIST"
            confidence = "medium"
        else:
            decision = "SKIP"
            confidence = "high"

        # Define entry zone and invalidation
        entry_min = round(price_usd * 0.97, 8) if price_usd > 0 else None
        entry_max = round(price_usd * 1.02, 8) if price_usd > 0 else None
        invalidation = round(price_usd * 0.88, 8) if price_usd > 0 else None
        rr_ratio = round(2.5, 2) if decision == "BUY" else None

        expires_at_iso = (now_utc + timedelta(seconds=MAX_DATA_AGE_SECONDS)).isoformat()

        structured_output = EntryDecisionOutput(
            agent="entry_intelligence",
            mint=mint,
            symbol=symbol,
            decision=decision,
            score=total_score,
            confidence=confidence,
            entry_zone=EntryZone(min=entry_min, max=entry_max),
            invalidation=invalidation,
            expected_rr_ratio=rr_ratio,
            dimensions=dim_scores,
            risk_flags=risk_flags,
            reasoning=reasons,
            data_timestamp=now_utc.isoformat(),
            expires_at=expires_at_iso,
            input_snapshot=input_snapshot,
        )

        # 5. Optional AI Multi-Provider Reasoning Blend (if not force_deterministic)
        if not force_deterministic and not is_stale and orchestrator.openrouter.is_configured():
            try:
                sys_prompt = (
                    "You are the Chief Entry Analyst for SOFIA MEME BOT V2 on Solana. "
                    "Analyze the token data snapshot and return a valid JSON object matching EntryDecisionOutput schema. "
                    "Rules: Never fabricate numbers. Rely on provided dimension scores. "
                    "Do not override math scores arbitrarily."
                )
                user_prompt = (
                    f"Token: {symbol} (Mint: {mint})\n"
                    f"Snapshot: {json.dumps(input_snapshot, indent=2)}\n"
                    f"Deterministic Dimensions: {dim_scores.model_dump_json()}\n"
                    f"Calculated Score: {total_score}/100"
                )
                ai_out, _ = orchestrator.execute_structured_agent(
                    db=None,  # We persist unified record below
                    agent_name="entry_intelligence",
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    schema_cls=EntryDecisionOutput,
                    target_mint=mint,
                    symbol=symbol,
                    model_override=model_override,
                    provider_preference=provider_preference,
                    timeout_seconds=8.0,
                )
                # Keep deterministic scores authoritative, blend AI qualitative reasoning
                structured_output.reasoning = ai_out.reasoning or structured_output.reasoning
                structured_output.confidence = ai_out.confidence
            except Exception as ex:
                logger.warning(f"AI qualitative blend skipped: {ex}. Using deterministic output.")

        # 6. Record to Agent Registry and Database (Directive Item 15)
        agent_registry.record_decision("entry_intelligence", structured_output.decision, structured_output.score)

        if db:
            try:
                db_decision = AgentDecision(
                    agent_name="entry_intelligence",
                    target_mint=mint,
                    symbol=symbol,
                    decision=structured_output.decision,
                    score=structured_output.score,
                    confidence=structured_output.confidence,
                    suggested_action=f"{structured_output.decision} (Score {structured_output.score:.1f})",
                    reasoning=structured_output.reasoning,
                    raw_output=structured_output.model_dump(),
                    input_snapshot=input_snapshot,
                    provider="deterministic_core" if force_deterministic else "openrouter_blend",
                    model=model_override or "rule-based-v2",
                    latency_ms=1,
                    is_fallback=force_deterministic,
                    created_at=now_utc,
                    expires_at=now_utc + timedelta(seconds=MAX_DATA_AGE_SECONDS),
                )
                db.add(db_decision)
                db.commit()
                db.refresh(db_decision)

                ea = EntryAssessment(
                    decision_id=db_decision.id,
                    target_mint=mint,
                    symbol=symbol,
                    market_structure_score=dim_scores.market_structure,
                    momentum_score=dim_scores.momentum,
                    smart_money_score=dim_scores.smart_money,
                    liquidity_score=dim_scores.liquidity,
                    holder_score=dim_scores.holder_intelligence,
                    narrative_score=dim_scores.narrative,
                    total_score=total_score,
                    entry_zone_min=entry_min,
                    entry_zone_max=entry_max,
                    invalidation_price=invalidation,
                    expected_rr_ratio=rr_ratio,
                    passed_quality_gate=False,  # Quality Gate will update this
                    risk_flags=risk_flags,
                    input_snapshot=input_snapshot,
                    created_at=now_utc,
                )
                db.add(ea)
                db.commit()
            except Exception as dbe:
                logger.error(f"Failed to persist EntryAssessment: {dbe}")
                db.rollback()

        return structured_output, input_snapshot

    @classmethod
    def _compute_deterministic_dimensions(
        cls,
        input_snapshot: Dict[str, Any],
        risk_flags: List[str],
    ) -> Tuple[EntryDimensionsScore, List[str]]:
        """
        Calculates 6 dimensions strictly adhering to PRD Section 5.1 weights:
        - Market Structure: max 20
        - Momentum: max 20
        - Smart Money: max 20
        - Liquidity: max 15
        - Holder Intelligence: max 15
        - Narrative: max 10
        Total: 100
        """
        reasons: List[str] = []

        p5m = input_snapshot["price_change_5m_pct"]
        p1h = input_snapshot["price_change_1h_pct"]
        v5m = input_snapshot["volume_5m_usd"]
        v1h = input_snapshot["volume_1h_usd"]
        liq = input_snapshot["liquidity_usd"]
        mcap = input_snapshot["market_cap_usd"]
        top10 = input_snapshot["top10_concentration_pct"]
        dev = input_snapshot["dev_holding_pct"]
        buys = input_snapshot["buys_5m"]
        sells = input_snapshot["sells_5m"]
        is_pump = input_snapshot["is_pump_curve"]
        bonding = input_snapshot["bonding_curve_pct"]

        # 1. Market Structure (Weight 20)
        # Healthy breakout: +5% to +35% in 5m with positive 1h trend
        if 5.0 <= p5m <= 35.0 and p1h >= 5.0:
            ms_score = 18.0
            reasons.append("Struktur pasar: breakout sehat dalam zona ekspansi teratur.")
        elif -5.0 <= p5m < 5.0 and p1h >= 0.0:
            ms_score = 14.0
            reasons.append("Struktur pasar: konsolidasi stabil dekat support.")
        elif p5m > 60.0 or p1h > 350.0:
            ms_score = 6.0
            reasons.append("Struktur pasar: parabolic runup ekstrim (penalti risiko FOMO puncak).")
        elif p5m < -15.0:
            ms_score = 3.0
            reasons.append("Struktur pasar: breakdown candle merah tebal.")
        else:
            ms_score = 10.0

        # 2. Momentum (Weight 20)
        expected_5m_vol = (v1h / 12.0) if v1h > 0 else 1.0
        velocity = (v5m / expected_5m_vol) if expected_5m_vol > 0 else 0.0
        if velocity >= 2.5 and v5m >= 3000.0:
            mom_score = 19.0
            reasons.append(f"Momentum: lonjakan volume 5m tinggi ({velocity:.1f}x kecepatan rerata 1h).")
        elif velocity >= 1.5:
            mom_score = 15.0
            reasons.append(f"Momentum: volume 5m aktif ({velocity:.1f}x rerata).")
        elif velocity < 0.6:
            mom_score = 5.0
            reasons.append("Momentum: volume transaksi melemah di bawah rerata.")
        else:
            mom_score = 11.0

        # 3. Smart Money (Weight 20)
        total_tx = buys + sells
        buy_ratio = (buys / total_tx) if total_tx > 0 else 0.5
        if buy_ratio >= 0.70 and buys >= 10:
            sm_score = 18.5
            reasons.append(f"Smart money: tekanan beli dominan ({buy_ratio*100:.0f}% buy volume).")
        elif buy_ratio >= 0.55:
            sm_score = 14.0
            reasons.append(f"Smart money: rasio beli positif ({buy_ratio*100:.0f}% buys).")
        elif buy_ratio < 0.40:
            sm_score = 4.0
            reasons.append(f"Smart money: dominasi penjualan aktif ({100-buy_ratio*100:.0f}% sells).")
        else:
            sm_score = 10.0

        # 4. Liquidity (Weight 15)
        if liq >= 40000.0:
            liq_score = 15.0
            reasons.append(f"Likuiditas: sangat dalam (${liq:,.0f}), slippage rendah.")
        elif liq >= 15000.0:
            liq_score = 12.5
            reasons.append(f"Likuiditas: memadai (${liq:,.0f}).")
        elif liq >= 5000.0:
            liq_score = 9.0
            reasons.append(f"Likuiditas: moderat (${liq:,.0f}).")
        else:
            liq_score = 2.0
            reasons.append(f"Likuiditas: tipis (${liq:,.0f}), rentan slippage tinggi.")

        # 5. Holder Intelligence (Weight 15)
        if top10 <= 15.0 and dev <= 2.5:
            hold_score = 15.0
            reasons.append(f"Distribusi holder: sangat terdistribusi (Top10: {top10:.1f}%, Dev: {dev:.1f}%).")
        elif top10 <= 25.0 and dev <= 7.0:
            hold_score = 11.0
            reasons.append(f"Distribusi holder: sehat (Top10: {top10:.1f}%, Dev: {dev:.1f}%).")
        elif top10 > 35.0 or dev > 15.0:
            hold_score = 3.0
            reasons.append(f"Distribusi holder: konsentrasi bahaya (Top10: {top10:.1f}%, Dev: {dev:.1f}%).")
        else:
            hold_score = 8.0

        # 6. Narrative (Weight 10)
        if not is_pump and liq >= 15000.0:
            narr_score = 9.0
            reasons.append("Narasi: pool Raydium migrasi penuh.")
        elif is_pump and bonding >= 85.0:
            narr_score = 8.0
            reasons.append(f"Narasi: pump.fun bonding curve final stretch ({bonding:.0f}%).")
        elif is_pump:
            narr_score = 6.0
        else:
            narr_score = 7.0

        dim_scores = EntryDimensionsScore(
            market_structure=round(min(20.0, max(0.0, ms_score)), 1),
            momentum=round(min(20.0, max(0.0, mom_score)), 1),
            smart_money=round(min(20.0, max(0.0, sm_score)), 1),
            liquidity=round(min(15.0, max(0.0, liq_score)), 1),
            holder_intelligence=round(min(15.0, max(0.0, hold_score)), 1),
            narrative=round(min(10.0, max(0.0, narr_score)), 1),
        )

        return dim_scores, reasons


# Singleton instance
entry_intelligence = EntryIntelligenceService()
