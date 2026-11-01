"""
Scanner Bridge for SOFIA MEME BOT V2.
Bridges existing DexScreener v1 & GMGN market data to V2 Entry Intelligence & Trade Quality Gate.
Preserves existing V1 scanning modules (Directive Item 4).
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.services import market, memecoins
from app.v2.services.entry_intelligence import entry_intelligence
from app.v2.core.quality_gate import quality_gate, QualityGateResult
from app.v2.ai.schemas import EntryDecisionOutput

logger = logging.getLogger("sofia.v2.scanner_bridge")


class CandidateScannerBridge:
    """
    Scans live Solana meme pools from DexScreener & GMGN radar,
    evaluating each candidate through the V2 Entry Intelligence Agent and Quality Gate.
    """

    @classmethod
    def scan_and_evaluate_candidates(
        cls,
        db: Optional[Session] = None,
        strategy_mode: str = "DEFAULT",
        limit: int = 15,
        force_deterministic: bool = True,
    ) -> List[Dict[str, Any]]:
        fx = market.get_fx_rate()
        usd_idr = fx.get("usd_idr", 16000.0)

        # 1. Fetch live pool candidates using existing scanner
        pulse = market.get_live_pulse_feed()
        raw_candidates = []
        if strategy_mode.upper() == "AGGRESSIVE":
            raw_candidates = pulse.get("new_creations") or []
            if not raw_candidates:
                raw_candidates = market.fetch_dexscreener_latest_new_creations(usd_idr, limit=limit)
        elif strategy_mode.upper() == "SAFE":
            raw_candidates = pulse.get("migrated") or pulse.get("final_stretch") or []
        else:
            raw_candidates = (pulse.get("final_stretch") or []) + (pulse.get("migrated") or []) + (pulse.get("new_creations") or [])

        # Filter Solana only and avoid duplicates
        seen_mints = set()
        clean_candidates = []
        for c in raw_candidates:
            mint = str(c.get("contract") or c.get("address") or "").strip()
            ch = str(c.get("chain") or "Solana").strip().lower()
            if ch == "solana" and len(mint) >= 32 and not mint.startswith("0x") and mint not in seen_mints:
                seen_mints.add(mint)
                clean_candidates.append(c)
                if len(clean_candidates) >= limit:
                    break

        evaluated_results: List[Dict[str, Any]] = []

        for cand in clean_candidates:
            mint = str(cand.get("contract") or cand.get("address") or "").strip()
            sym = str(cand.get("base_symbol") or cand.get("symbol") or "MEME").upper()

            # Audit on-chain safety using existing RugCheck module
            rug = memecoins.analyze_rug_check(mint)

            # Enrich candidate dict with rugcheck findings
            merged_data = {
                **cand,
                "top10_concentration_pct": rug.get("top10_pct", 20.0),
                "dev_holding_pct": rug.get("dev_holding_pct", 0.0),
                "mint_revoked": rug.get("mint_revoked", False),
                "freeze_revoked": rug.get("freeze_revoked", False),
                "lp_burned": rug.get("lp_burned", False),
                "honeypot": rug.get("honeypot", False),
                "data_timestamp": cand.get("data_timestamp") or cand.get("updated_at"),
            }

            # 2. Evaluate with Entry Intelligence Agent
            entry_dec, input_snap = entry_intelligence.evaluate_candidate(
                token_data=merged_data,
                db=db,
                force_deterministic=force_deterministic,
            )

            # 3. Evaluate with Trade Quality Gate
            qg_res = quality_gate.evaluate(
                entry_decision=entry_dec,
                risk_data=merged_data,
                strategy_mode=strategy_mode,
                db=db,
            )

            evaluated_results.append({
                "mint": mint,
                "symbol": sym,
                "decision": entry_dec.decision,
                "score": entry_dec.score,
                "confidence": entry_dec.confidence,
                "dimensions": entry_dec.dimensions.model_dump() if entry_dec.dimensions else None,
                "quality_gate": {
                    "passed": qg_res.passed,
                    "verdict": qg_res.verdict,
                    "rejection_reasons": qg_res.rejection_reasons,
                    "estimated_slippage_pct": qg_res.estimated_slippage_pct,
                },
                "risk_assessment": qg_res.risk_assessment.model_dump() if qg_res.risk_assessment else None,
                "entry_zone": entry_dec.entry_zone.model_dump(),
                "invalidation": entry_dec.invalidation,
                "risk_flags": entry_dec.risk_flags,
                "reasoning": entry_dec.reasoning[:3],
                "input_snapshot": input_snap,
                "expires_at": entry_dec.expires_at,
            })

        return evaluated_results


# Singleton
scanner_bridge = CandidateScannerBridge()
