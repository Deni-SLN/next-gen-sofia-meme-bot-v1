"""
Trade Quality Gate for SOFIA MEME BOT V2.
Strictly adheres to:
- PRD Section 5.2 (Entry Conditions & Trade Quality Gate)
- PRD Section 8.1 & 8.2 (Decision Authority & Conflict Resolution)
- Directive Phase 2 Items 11, 13 (AI cannot override Risk Engine veto)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.v2.ai.schemas import EntryDecisionOutput, RiskAssessmentOutput
from app.v2.db.models import EntryAssessment

logger = logging.getLogger("sofia.v2.quality_gate")


class QualityGateResult(BaseModel):
    passed: bool
    verdict: str  # APPROVED, REJECT_LOW_SCORE, REJECT_RISK_VETO, REJECT_STALE_SIGNAL, REJECT_SLIPPAGE
    rejection_reasons: List[str] = []
    risk_assessment: Optional[RiskAssessmentOutput] = None
    jupiter_quote_simulated: bool = False
    estimated_slippage_pct: float = 0.0
    evaluated_at: str


class TradeQualityGate:
    """
    Deterministic safety gate enforcing hard risk invariants before any trade can be dispatched.
    AI performs market interpretation, but Deterministic Rules hold absolute veto authority.
    """

    MIN_ENTRY_SCORE = 75.0
    MAX_PERMITTED_SLIPPAGE_PCT = 3.5

    @classmethod
    def evaluate(
        cls,
        entry_decision: EntryDecisionOutput,
        risk_data: Dict[str, Any],
        strategy_mode: str = "DEFAULT",
        db: Optional[Session] = None,
    ) -> QualityGateResult:
        now_utc = datetime.now(timezone.utc)
        rejection_reasons: List[str] = []

        # 1. Decision & Score Threshold Check (PRD Section 5.1)
        if entry_decision.decision != "BUY":
            rejection_reasons.append(f"AI Decision is {entry_decision.decision} (not BUY)")
        if entry_decision.score < cls.MIN_ENTRY_SCORE:
            rejection_reasons.append(f"Score {entry_decision.score:.1f} below minimum quality threshold ({cls.MIN_ENTRY_SCORE})")

        # 2. Signal Freshness & Expiration Check (PRD Section 5.4 & Directive Item 10)
        try:
            exp_dt = datetime.fromisoformat(entry_decision.expires_at.replace("Z", "+00:00"))
            if now_utc > exp_dt:
                rejection_reasons.append("Signal has expired (>180s old)")
        except Exception:
            pass

        # 3. Deterministic Risk Engine Verification & Absolute Veto (Directive Item 13)
        # Thresholds depend on strategy preset
        mode_upper = strategy_mode.upper()
        if mode_upper == "SAFE":
            min_liq = 20000.0
            max_top10 = 25.0
            max_dev = 5.0
        elif mode_upper == "AGGRESSIVE":
            min_liq = 2000.0
            max_top10 = 35.0
            max_dev = 15.0
        else:  # DEFAULT
            min_liq = 5000.0
            max_top10 = 30.0
            max_dev = 10.0

        liq_usd = float(risk_data.get("liquidity_usd") or 0.0)
        top10_pct = float(risk_data.get("top10_concentration_pct") or risk_data.get("top10_pct") or 0.0)
        dev_pct = float(risk_data.get("dev_holding_pct") or risk_data.get("dev_holding") or 0.0)
        mint_revoked = bool(risk_data.get("mint_revoked") or risk_data.get("mint_authority_disabled") or False)
        freeze_revoked = bool(risk_data.get("freeze_revoked") or risk_data.get("freeze_authority_disabled") or False)
        lp_burned = bool(risk_data.get("lp_burned") or False)
        is_honeypot = bool(risk_data.get("honeypot") or False)

        risk_flags: List[str] = []
        veto_triggered = False
        veto_reason = None

        if is_honeypot:
            veto_triggered = True
            veto_reason = "HONEYPOT_DETECTED"
            risk_flags.append(veto_reason)
            rejection_reasons.append("HARD VETO: Token terdeteksi sebagai Honeypot / tidak bisa dijual!")

        if not mint_revoked:
            veto_triggered = True
            veto_reason = "MINT_AUTHORITY_STILL_ACTIVE"
            risk_flags.append(veto_reason)
            rejection_reasons.append("HARD VETO: Mint Authority masih aktif (developer dapat mencetak token tak terbatas)!")

        if not freeze_revoked:
            veto_triggered = True
            veto_reason = "FREEZE_AUTHORITY_STILL_ACTIVE"
            risk_flags.append(veto_reason)
            rejection_reasons.append("HARD VETO: Freeze Authority masih aktif (wallet dapat dibekukan)!")

        if not lp_burned and liq_usd > 0 and mode_upper in ("SAFE", "DEFAULT"):
            veto_triggered = True
            veto_reason = "LP_NOT_BURNED_OR_LOCKED"
            risk_flags.append(veto_reason)
            rejection_reasons.append("HARD VETO: Likuiditas LP belum dibakar atau dikunci!")

        if liq_usd < min_liq:
            veto_triggered = True
            veto_reason = f"INSUFFICIENT_LIQUIDITY (${liq_usd:,.0f} < ${min_liq:,.0f})"
            risk_flags.append(veto_reason)
            rejection_reasons.append(f"HARD VETO: Likuiditas ${liq_usd:,.0f} di bawah batas minimal mode {mode_upper} (${min_liq:,.0f})!")

        if top10_pct > max_top10:
            veto_triggered = True
            veto_reason = f"EXCESSIVE_TOP10_CONCENTRATION ({top10_pct:.1f}% > {max_top10:.1f}%)"
            risk_flags.append(veto_reason)
            rejection_reasons.append(f"HARD VETO: Top 10 Holder menguasai {top10_pct:.1f}% suplai (maksimal {max_top10:.1f}%)!")

        if dev_pct > max_dev:
            veto_triggered = True
            veto_reason = f"EXCESSIVE_DEV_HOLDING ({dev_pct:.1f}% > {max_dev:.1f}%)"
            risk_flags.append(veto_reason)
            rejection_reasons.append(f"HARD VETO: Wallet Developer memegang {dev_pct:.1f}% suplai (maksimal {max_dev:.1f}%)!")

        # 4. Simulated Jupiter Quote & Slippage Check (PRD Section 10.1)
        est_slippage = 1.0
        if liq_usd > 0 and liq_usd < 10000.0:
            est_slippage = 2.5
        elif liq_usd >= 10000.0:
            est_slippage = 0.8
        else:
            est_slippage = 5.0

        if est_slippage > cls.MAX_PERMITTED_SLIPPAGE_PCT:
            rejection_reasons.append(f"Estimated slippage ({est_slippage:.1f}%) exceeds safety ceiling ({cls.MAX_PERMITTED_SLIPPAGE_PCT}%)")

        risk_score = 100.0 - (len(risk_flags) * 20.0)
        risk_output = RiskAssessmentOutput(
            agent="risk_analyst",
            mint=entry_decision.mint,
            symbol=entry_decision.symbol,
            is_safe=not veto_triggered,
            veto_triggered=veto_triggered,
            veto_reason=veto_reason,
            risk_score=max(0.0, risk_score),
            liquidity_usd=liq_usd,
            top10_concentration_pct=top10_pct,
            mint_authority_disabled=mint_revoked,
            freeze_authority_disabled=freeze_revoked,
            lp_burned=lp_burned,
            flags=risk_flags,
            data_timestamp=now_utc.isoformat(),
        )

        # 5. Final Quality Gate Verdict
        passed = (len(rejection_reasons) == 0) and not veto_triggered
        if passed:
            verdict = "APPROVED"
        elif veto_triggered:
            verdict = "REJECT_RISK_VETO"
        elif entry_decision.score < cls.MIN_ENTRY_SCORE:
            verdict = "REJECT_LOW_SCORE"
        else:
            verdict = "REJECT_SAFETY_CHECK"

        # Update entry_decision with quality gate status
        entry_decision.quality_gate_passed = passed
        entry_decision.quality_gate_reason = verdict if passed else "; ".join(rejection_reasons[:2])

        # 6. Update Database EntryAssessment record if available
        if db:
            try:
                stmt = (
                    select(EntryAssessment)
                    .where(EntryAssessment.target_mint == entry_decision.mint)
                    .order_by(EntryAssessment.id.desc())
                    .limit(1)
                )
                ea = db.execute(stmt).scalar_one_or_none()
                if ea:
                    ea.passed_quality_gate = passed
                    ea.rejection_reason = None if passed else "; ".join(rejection_reasons[:2])
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update EntryAssessment quality gate flag: {e}")
                db.rollback()

        return QualityGateResult(
            passed=passed,
            verdict=verdict,
            rejection_reasons=rejection_reasons,
            risk_assessment=risk_output,
            jupiter_quote_simulated=True,
            estimated_slippage_pct=est_slippage,
            evaluated_at=now_utc.isoformat(),
        )


# Singleton
quality_gate = TradeQualityGate()
