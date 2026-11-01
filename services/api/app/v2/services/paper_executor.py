"""
PAPER Execution Simulator for SOFIA MEME BOT V2.
Enforces Directive Item 5 & 16:
- Zero modifications to LIVE trading execution.
- Integrates with existing PAPER trading balance & PortfolioHolding.
- Emits PositionEvent and initial DecisionJournal record.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import PortfolioHolding, Trade, Wallet
from app.v2.db.models import PositionEvent, DecisionJournal
from app.v2.ai.schemas import EntryDecisionOutput
from app.v2.core.quality_gate import QualityGateResult
from app.services import market

logger = logging.getLogger("sofia.v2.paper_executor")


class V2PaperExecutor:
    """
    Executes simulated purchases for V2 AI-approved tokens strictly in PAPER mode.
    """

    @classmethod
    def execute_paper_entry(
        cls,
        db: Session,
        entry_decision: EntryDecisionOutput,
        quality_gate_result: QualityGateResult,
        allocation_usd: float = 1.0,
    ) -> Dict[str, Any]:
        if not quality_gate_result.passed:
            raise ValueError(f"Quality Gate rejected token: {quality_gate_result.verdict}")

        if entry_decision.decision != "BUY":
            raise ValueError(f"Cannot execute non-BUY decision: {entry_decision.decision}")

        now_utc = datetime.now(timezone.utc)
        fx = market.get_fx_rate()
        usd_idr = fx.get("usd_idr", 16000.0)

        sym = entry_decision.symbol
        mint = entry_decision.mint
        price_usd = float(entry_decision.entry_zone.max or 0.0)
        if price_usd <= 0:
            snap = entry_decision.input_snapshot or {}
            price_usd = float(snap.get("price_usd") or 0.0001)

        # 1. Realistic execution costs modeling (PRD Section 10.3)
        slip_pct = quality_gate_result.estimated_slippage_pct
        effective_price = price_usd * (1.0 + (slip_pct / 100.0))
        dex_fee_usd = round(allocation_usd * 0.0025, 6)
        gas_fee_usd = 0.0016
        net_allocation_usd = max(0.1, allocation_usd - dex_fee_usd - gas_fee_usd)
        token_qty = round(net_allocation_usd / effective_price, 4) if effective_price > 0 else 1000.0

        # 2. Update or create PortfolioHolding in PAPER mode
        stmt = select(PortfolioHolding).where(PortfolioHolding.symbol == sym, PortfolioHolding.mode == "PAPER")
        holding = db.execute(stmt).scalar_one_or_none()
        if not holding:
            holding = PortfolioHolding(
                symbol=sym,
                mode="PAPER",
                quantity=token_qty,
                avg_entry_price=effective_price,
                current_price=price_usd,
                entry_costs_usd=dex_fee_usd + gas_fee_usd,
                liquidity_usd=float((entry_decision.input_snapshot or {}).get("liquidity_usd", 10000.0)),
                updated_at=now_utc,
            )
            db.add(holding)
        else:
            tot_qty = holding.quantity + token_qty
            tot_cost = (holding.quantity * holding.avg_entry_price) + (token_qty * effective_price)
            holding.avg_entry_price = round(tot_cost / tot_qty, 8) if tot_qty > 0 else effective_price
            holding.quantity = tot_qty
            holding.current_price = price_usd
            holding.entry_costs_usd += (dex_fee_usd + gas_fee_usd)
            holding.updated_at = now_utc

        # 3. Record Trade ledger (Rule 1: BUY has pnl = 0.0)
        paper_trade = Trade(
            symbol=sym,
            side="buy",
            quantity=token_qty,
            price=effective_price,
            total=allocation_usd,
            mode="PAPER",
            status="closed",  # Buy order fill is settled
            pnl=0.0,          # Zero dummy data: entry has zero realized PnL
            market_price=price_usd,
            slippage_pct=slip_pct,
            dex_fee_usd=dex_fee_usd,
            gas_fee_usd=gas_fee_usd,
            chain="Solana",
            tx_hash=f"paper_v2_{int(now_utc.timestamp())}_{sym}",
            notes=f"V2 AI Entry Approved (Score: {entry_decision.score:.1f}, Dim: MS={entry_decision.dimensions.market_structure if entry_decision.dimensions else 0})",
            opened_at=now_utc,
            closed_at=now_utc,
        )
        db.add(paper_trade)
        db.flush()

        # 4. Record PositionEvent lifecycle audit
        pos_event = PositionEvent(
            symbol=sym,
            mint=mint,
            mode="PAPER",
            event_type="V2_AI_APPROVED_ENTRY",
            quantity=token_qty,
            price=effective_price,
            realized_pnl_usd=0.0,
            tx_hash=paper_trade.tx_hash,
            details={
                "entry_score": entry_decision.score,
                "confidence": entry_decision.confidence,
                "dimensions": entry_decision.dimensions.model_dump() if entry_decision.dimensions else None,
                "quality_gate_verdict": quality_gate_result.verdict,
                "input_snapshot": entry_decision.input_snapshot,
            },
            created_at=now_utc,
        )
        db.add(pos_event)

        # 5. Record Initial DecisionJournal entry for feedback learning (PRD Section 9.2)
        journal_entry = DecisionJournal(
            trade_id=paper_trade.id,
            symbol=sym,
            mint=mint,
            mode="PAPER",
            entry_score=entry_decision.score,
            initial_risk_pct=slip_pct,
            mfe_pct=0.0,
            mae_pct=0.0,
            profit_capture_ratio=0.0,
            final_realized_pnl_usd=0.0,
            final_realized_pnl_pct=0.0,
            exit_reason="POSITION_OPEN",
            ai_post_mortem=f"Approved by Entry Intelligence (Score: {entry_decision.score:.1f}) and verified by Trade Quality Gate.",
            created_at=now_utc,
        )
        db.add(journal_entry)

        db.commit()

        return {
            "status": "success",
            "mode": "PAPER",
            "trade_id": paper_trade.id,
            "symbol": sym,
            "mint": mint,
            "quantity": token_qty,
            "effective_price": effective_price,
            "allocation_usd": allocation_usd,
            "allocation_idr": round(allocation_usd * usd_idr, 0),
            "fees_usd": round(dex_fee_usd + gas_fee_usd, 5),
            "quality_gate_verdict": quality_gate_result.verdict,
            "executed_at": now_utc.isoformat(),
        }


# Singleton
paper_executor = V2PaperExecutor()
