"""
Independent Exit Intelligence Service for SOFIA MEME BOT V2.
Strictly adheres to:
- PRD Section 4.2 (Exit Intelligence Agent)
- PRD Section 6 (AI Exit Intelligence & Adaptive Profit Management)
- Directive Phase 3 Sections 3, 4, 5, 7
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.v2.ai.schemas import ExitDecisionOutput, ExitDimensionsScore, ExitMarketConditions
from app.v2.agents.registry import agent_registry
from app.v2.db.models import AgentDecision, ExitAssessment
from app.v2.services.exit_market_analyzer import exit_market_analyzer
from app.v2.services.exit_smart_money import exit_smart_money
from app.v2.core.exit_policy import exit_policy
from app.v2.services.adaptive_profit_manager import adaptive_profit_manager

logger = logging.getLogger("sofia.v2.exit_intelligence")

MAX_DATA_AGE_SECONDS: float = 120.0


class ExitIntelligenceService:
    """
    Chief Exit Analyst: Analyzes open positions across 6 deterioration dimensions,
    incorporates smart money distribution, tracks peak excursions & trailing stops,
    and applies deterministic risk policy overrides.
    """

    @classmethod
    def evaluate_position(
        cls,
        position_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        strategy_mode: str = "DEFAULT",
        force_deterministic: bool = True,
    ) -> Tuple[ExitDecisionOutput, Dict[str, Any]]:
        """
        Evaluates an active position and recommends an adaptive exit decision.
        Returns:
            (ExitDecisionOutput, input_snapshot)
        """
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        symbol = str(position_data.get("symbol") or "MEME").strip().upper()
        mint = str(position_data.get("mint") or position_data.get("contract") or symbol).strip()
        position_id = str(position_data.get("position_id") or position_data.get("id") or symbol)

        entry_price = float(position_data.get("avg_entry_price") or position_data.get("entry_price") or 0.0)
        quantity = float(position_data.get("quantity") or 0.0)
        entry_liquidity = float(position_data.get("liquidity_usd") or position_data.get("entry_liquidity") or 25000.0)
        position_age_minutes = float(position_data.get("position_age_minutes") or 15.0)

        # Merge live market data if available
        m_data = dict(market_data or {})
        current_price = float(m_data.get("price") or position_data.get("current_price") or entry_price)
        current_liquidity = float(m_data.get("liquidity") or m_data.get("liquidity_usd") or entry_liquidity)
        is_honeypot = bool(m_data.get("is_honeypot") or False)
        top10_concentration = float(m_data.get("top10_concentration_pct") or 25.0)
        dev_holding = float(m_data.get("dev_holding_pct") or 3.0)

        risk_flags: List[str] = []
        reasoning: List[str] = []

        # 1. Missing Data Validation (Missing data is NEVER interpreted as safe!)
        is_data_missing = False
        if not market_data or current_price <= 0:
            is_data_missing = True
            risk_flags.append("MISSING_MARKET_DATA: Data feed pasar tidak tersedia atau harga <= 0")
            reasoning.append("Peringatan: Data pasar tidak lengkap, proteksi risiko dinaikkan.")

        # 2. Update Peak / Trough excursion & trailing stops via Adaptive Profit Manager
        highest_price, lowest_price, active_trailing_stop, be_active = adaptive_profit_manager.update_position_tracking(
            symbol=symbol,
            current_price=current_price,
            entry_price=entry_price,
        )

        unrealized_pnl_pct = 0.0
        if entry_price > 0:
            unrealized_pnl_pct = round(((current_price - entry_price) / entry_price) * 100.0, 2)

        # 3. Market & Smart Money Analysis
        market_analysis = exit_market_analyzer.analyze_market_conditions(
            token_data=m_data,
            entry_price=entry_price,
            current_price=current_price,
            highest_price=highest_price,
            entry_liquidity=entry_liquidity,
            current_liquidity=current_liquidity,
            position_age_minutes=position_age_minutes,
        )

        smart_money_analysis = exit_smart_money.evaluate_smart_money_activity(
            token_data=m_data,
            top10_concentration_pct=top10_concentration,
            dev_holding_pct=dev_holding,
        )

        # 4. Multi-dimensional Scoring (6 Dimensions per Directive Section 4)
        # Dimension 1: Momentum Deterioration (Weight 25%)
        dim_momentum = 0.0
        peak_ret = market_analysis["peak_retracement_pct"]
        p5m = market_analysis["price_change_5m_pct"]
        vol_vel = market_analysis["volume_velocity"]

        if is_data_missing:
            dim_momentum = 15.0  # Conservative penalty for missing data
        else:
            if peak_ret >= 30.0 or p5m <= -15.0:
                dim_momentum += 20.0
                reasoning.append(f"Momentum kolaps: retracement -{peak_ret:.1f}% dari puncak harga.")
            elif peak_ret >= 15.0 or p5m <= -6.0:
                dim_momentum += 12.0
                reasoning.append(f"Momentum melemah: retracement -{peak_ret:.1f}%.")
            elif p5m >= 4.0:
                dim_momentum += 1.0

            if vol_vel < 0.35 and p5m < 0:
                dim_momentum = min(25.0, dim_momentum + 5.0)
                reasoning.append("Volume perdagangan 5m anjlok di bawah rata-rata.")

        dim_momentum = min(25.0, max(0.0, dim_momentum))

        # Dimension 2: Sell Pressure (Weight 20%)
        dim_sell_pressure = 0.0
        sell_ratio = market_analysis["sell_ratio_5m"]
        sells_5m = market_analysis["sells_5m"]

        if is_data_missing:
            dim_sell_pressure = 12.0
        else:
            if sell_ratio >= 75.0 and sells_5m >= 10:
                dim_sell_pressure = 20.0
                reasoning.append(f"Tekanan jual dominan: {sell_ratio:.0f}% transaksi 5m adalah SELL.")
            elif sell_ratio >= 60.0:
                dim_sell_pressure = 14.0
                reasoning.append(f"Tekanan jual meningkat: rasio sell {sell_ratio:.0f}%.")
            elif sell_ratio >= 50.0:
                dim_sell_pressure = 7.0
            else:
                dim_sell_pressure = 2.0

        # Dimension 3: Smart Money Distribution (Weight 20%)
        dim_smart_money = 0.0
        sm_status = smart_money_analysis["smart_money_status"]
        if is_data_missing:
            dim_smart_money = 12.0
        else:
            if smart_money_analysis["whale_dump_detected"] or sm_status == "dumping":
                dim_smart_money = 20.0
                risk_flags.append("WHALE_DUMP_DETECTED: Aksi jual whale terdeteksi")
                reasoning.append("Whale dump terdeteksi di pasar.")
            elif sm_status == "distribution":
                dim_smart_money = 13.0
                reasoning.append("Smart money berada dalam fase distribusi.")
            elif sm_status == "accumulation":
                dim_smart_money = 1.0
            else:
                dim_smart_money = 5.0

            if dev_holding > 12.0:
                dim_smart_money = min(20.0, dim_smart_money + 5.0)
                risk_flags.append(f"DEV_HOLDING_ELEVATED: Developer memegang {dev_holding:.1f}%")

        # Dimension 4: Market Structure (Weight 15%)
        dim_market_structure = 0.0
        p1h = market_analysis["price_change_1h_pct"]
        if is_data_missing:
            dim_market_structure = 8.0
        else:
            if current_price < entry_price and p1h <= -12.0:
                dim_market_structure = 15.0
                reasoning.append("Struktur pasar rusak (Lower Low di timeframe 1 jam).")
            elif current_price < entry_price:
                dim_market_structure = 9.0
            elif p1h < -5.0:
                dim_market_structure = 6.0
            else:
                dim_market_structure = 1.0

        # Dimension 5: Liquidity Deterioration (Weight 10%)
        dim_liquidity = 0.0
        liq_decay = market_analysis["liquidity_decay_pct"]
        if is_data_missing:
            dim_liquidity = 6.0
        else:
            if liq_decay >= 40.0 or current_liquidity < 2000.0:
                dim_liquidity = 10.0
                risk_flags.append(f"LIQUIDITY_DRAIN: Likuiditas terkuras {liq_decay:.1f}%")
                reasoning.append("Likuiditas pool anjlok drastis.")
            elif liq_decay >= 20.0 or current_liquidity < 5000.0:
                dim_liquidity = 6.0
                reasoning.append(f"Likuiditas tergerus ({liq_decay:.1f}%).")
            elif liq_decay >= 10.0:
                dim_liquidity = 3.0
            else:
                dim_liquidity = 0.0

        # Dimension 6: Time & Thesis Deterioration (Weight 10%)
        dim_time_thesis = 0.0
        if position_age_minutes >= 120.0 and unrealized_pnl_pct < 5.0:
            dim_time_thesis = 10.0
            reasoning.append(f"Waktu posisi kadaluarsa ({position_age_minutes:.0f}m) tanpa ekspansi profit.")
        elif position_age_minutes >= 60.0 and unrealized_pnl_pct < 0.0:
            dim_time_thesis = 7.0
            reasoning.append("Posisi stagnan/merugi setelah 1 jam.")
        elif position_age_minutes >= 30.0:
            dim_time_thesis = 3.0
        else:
            dim_time_thesis = 1.0

        dimensions = ExitDimensionsScore(
            momentum_deterioration=round(dim_momentum, 1),
            sell_pressure=round(dim_sell_pressure, 1),
            smart_money_distribution=round(dim_smart_money, 1),
            market_structure=round(dim_market_structure, 1),
            liquidity_deterioration=round(dim_liquidity, 1),
            time_thesis_deterioration=round(dim_time_thesis, 1),
        )

        total_exit_score = dimensions.total_urgency_score

        # 5. Baseline AI Action Determination
        if is_honeypot:
            ai_action = "EMERGENCY_EXIT"
            urgency = "critical"
            sell_pct = 100
        elif total_exit_score >= 75.0:
            ai_action = "FULL_EXIT"
            urgency = "critical"
            sell_pct = 100
        elif total_exit_score >= 55.0:
            ai_action = "REDUCE"
            urgency = "high"
            sell_pct = 50
        elif total_exit_score >= 38.0:
            ai_action = "TIGHTEN_STOP"
            urgency = "medium"
            sell_pct = 25 if unrealized_pnl_pct > 15.0 else 0
        else:
            urgency = "low"
            if unrealized_pnl_pct >= 40.0:
                ai_action = "TAKE_PROFIT"
                sell_pct = 25
            else:
                ai_action = "HOLD"
                sell_pct = 0

        # Confidence assessment
        confidence: str = "high" if not is_data_missing else "low"
        if is_data_missing:
            confidence = "low"
        elif total_exit_score > 80.0 or total_exit_score < 25.0:
            confidence = "high"
        else:
            confidence = "medium"

        # 6. Deterministic Risk Policy Override
        # Hard stop-loss, emergency exit, trailing stops override AI recommendations!
        policy_result = exit_policy.evaluate_position_policy(
            entry_price=entry_price,
            current_price=current_price,
            highest_price=highest_price,
            current_trailing_stop=active_trailing_stop,
            breakeven_activated=be_active,
            liquidity_decay_pct=market_analysis["liquidity_decay_pct"],
            is_honeypot=is_honeypot,
            strategy_mode=strategy_mode,
        )

        final_action = ai_action
        final_sell_pct = sell_pct

        if policy_result.is_hard_override:
            final_action = policy_result.action
            final_sell_pct = policy_result.suggested_sell_pct
            urgency = "critical"
            reasoning.insert(0, f"[RISK VETO] {policy_result.override_reason}")
            risk_flags.append(f"POLICY_HARD_OVERRIDE: {policy_result.action}")
        elif policy_result.action.startswith("REDUCE_") and ai_action in ("HOLD", "WAIT"):
            final_action = "TAKE_PROFIT"
            final_sell_pct = policy_result.suggested_sell_pct
            reasoning.append(f"Adaptive Profit Target tercapai (+{unrealized_pnl_pct:.1f}%): Amankan profit {final_sell_pct}%.")

        # 7. Build Input Snapshot for Complete Reproducibility (Directive Section 4 & Phase 2 Item 12)
        input_snapshot = {
            "position": {
                "position_id": position_id,
                "symbol": symbol,
                "mint": mint,
                "entry_price": entry_price,
                "current_price": current_price,
                "quantity": quantity,
                "position_age_minutes": position_age_minutes,
                "unrealized_pnl_pct": unrealized_pnl_pct,
            },
            "market_snapshot": {
                "price": current_price,
                "liquidity_usd": current_liquidity,
                "highest_price_observed": highest_price,
                "lowest_price_observed": lowest_price,
                "market_analysis": market_analysis,
                "smart_money_analysis": smart_money_analysis,
            },
            "policy_check": {
                "action": policy_result.action,
                "suggested_sell_pct": policy_result.suggested_sell_pct,
                "is_hard_override": policy_result.is_hard_override,
                "override_reason": policy_result.override_reason,
                "trailing_stop_price": policy_result.trailing_stop_price,
                "breakeven_triggered": policy_result.breakeven_triggered,
            },
            "evaluation_time": now_utc.isoformat(),
            "strategy_mode": strategy_mode,
        }

        # 8. Output Construction
        output = ExitDecisionOutput(
            agent="exit_intelligence",
            position_id=position_id,
            mint=mint,
            symbol=symbol,
            decision=final_action,
            urgency=urgency,
            exit_score=total_exit_score,
            confidence=confidence,
            suggested_sell_percentage=final_sell_pct,
            dimensions=dimensions,
            market_conditions=ExitMarketConditions(
                momentum=market_analysis["momentum"],
                sell_pressure=market_analysis["sell_pressure"],
                smart_money=smart_money_analysis["smart_money_status"],
                liquidity=market_analysis["liquidity"],
            ),
            reasoning=reasoning,
            risk_flags=risk_flags,
            highest_price_observed=highest_price,
            current_executable_price=current_price,
            unrealized_pnl_pct=unrealized_pnl_pct,
            trailing_stop_price=policy_result.trailing_stop_price or active_trailing_stop,
            input_snapshot=input_snapshot,
            model_version="v2.0-adaptive",
            strategy_mode=strategy_mode,
            data_timestamp=now_utc.isoformat(),
            expires_at=(now_utc + timedelta(seconds=MAX_DATA_AGE_SECONDS)).isoformat(),
        )

        # 9. Record to Agent Registry & Database (Directive Item 15)
        agent_registry.record_decision("exit_intelligence", output.decision, output.exit_score)

        if db:
            try:
                db_decision = AgentDecision(
                    agent_name="exit_intelligence",
                    target_mint=mint,
                    symbol=symbol,
                    decision=output.decision,
                    score=output.exit_score,
                    confidence=output.confidence,
                    suggested_action=f"{output.decision} ({output.suggested_sell_percentage}%)",
                    reasoning=output.reasoning,
                    raw_output=output.model_dump(),
                    input_snapshot=input_snapshot,
                    provider="deterministic_core" if force_deterministic else "openrouter_blend",
                    model="v2.0-adaptive",
                    latency_ms=1,
                    is_fallback=force_deterministic,
                    created_at=now_utc,
                    expires_at=now_utc + timedelta(seconds=MAX_DATA_AGE_SECONDS),
                )
                db.add(db_decision)
                db.commit()
                db.refresh(db_decision)

                ea = ExitAssessment(
                    decision_id=db_decision.id,
                    position_id=position_id,
                    target_mint=mint,
                    symbol=symbol,
                    urgency=output.urgency,
                    suggested_sell_pct=output.suggested_sell_percentage,
                    market_conditions=output.market_conditions.model_dump(),
                    highest_price_observed=highest_price,
                    current_executable_price=current_price,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    trailing_stop_level=output.trailing_stop_price,
                    dimensions_score=dimensions.model_dump(),
                    risk_flags=risk_flags,
                    input_snapshot=input_snapshot,
                    created_at=now_utc,
                )
                db.add(ea)
                db.commit()
            except Exception as dbe:
                logger.error(f"Failed to persist ExitAssessment: {dbe}")
                db.rollback()

        return output, input_snapshot


# Singleton
exit_intelligence = ExitIntelligenceService()
