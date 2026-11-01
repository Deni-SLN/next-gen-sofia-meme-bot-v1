"""
Partial Exit Manager for SOFIA MEME BOT V2.
Handles balance-reconciled partial exits (25%, 50%, 75%, 100%),
realized PnL accounting, position event recording, and Decision Journal post-mortem metrics.
Fulfills PRD Section 6.3 & Directive Section 5.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.db.models import PortfolioHolding, Trade
from app.v2.db.models import PositionEvent, DecisionJournal
from app.v2.services.adaptive_profit_manager import adaptive_profit_manager
from app.v2.core.exit_policy import exit_policy, ExitPolicy
from app.services import portfolio

logger = logging.getLogger("sofia.v2.partial_exit_manager")


class PartialExitManager:
    """
    Executes partial or full liquidations with balance reconciliation,
    precise PnL calculation, event logging, and Decision Journal recording.
    """

    ALLOWED_SELL_PERCENTAGES = [25.0, 50.0, 75.0, 100.0]

    @classmethod
    def execute_partial_exit(
        cls,
        db: Session,
        symbol: str,
        sell_pct: float,
        exit_reason: str = "AI_RECOMMENDED_EXIT",
        mode: str = "PAPER",
        exit_decision_id: Optional[int] = None,
        exit_score: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executes a partial or full liquidation for an active holding.
        Reconciles balance, calculates realized PnL, logs PositionEvent,
        and records DecisionJournal with MFE/MAE/Profit Capture Ratio.
        """
        clean_sym = symbol.strip()
        trade_mode = mode.upper()

        # 1. Balance reconciliation: locate holding
        q = select(PortfolioHolding).where(
            or_(
                PortfolioHolding.symbol == clean_sym,
                func.upper(PortfolioHolding.symbol) == clean_sym.upper(),
            ),
            PortfolioHolding.mode == trade_mode,
        )
        holding = db.execute(q).scalars().first()
        if not holding or float(holding.quantity or 0.0) <= 0:
            raise ValueError(f"Posisi {clean_sym} ({trade_mode}) tidak ditemukan di portofolio atau saldo 0.")

        initial_qty = float(holding.quantity)
        entry_price = float(holding.avg_entry_price or 0.0)

        # Sanitize sell percentage
        pct = max(1.0, min(100.0, float(sell_pct)))

        # 2. Retrieve excursion metrics (MFE / MAE)
        highest_obs, lowest_obs, trailing_stop, be_active = adaptive_profit_manager.get_position_tracking(clean_sym)
        if highest_obs <= 0:
            highest_obs = max(entry_price, float(holding.current_price or entry_price))
        if lowest_obs <= 0:
            lowest_obs = min(entry_price, float(holding.current_price or entry_price))

        mfe_pct = max(0.0, ((highest_obs - entry_price) / entry_price) * 100.0) if entry_price > 0 else 0.0
        mae_pct = min(0.0, ((lowest_obs - entry_price) / entry_price) * 100.0) if entry_price > 0 else 0.0

        # 3. Dispatch execution through portfolio service
        sell_res = portfolio.sell_holding(db=db, symbol=clean_sym, sell_pct=pct, mode=trade_mode)

        qty_sold = float(sell_res.get("qty_sold") or 0.0)
        sell_price = float(sell_res.get("sell_price_usd") or sell_res.get("market_price_usd") or 0.0)
        realized_pnl_usd = float(sell_res.get("realized_pnl_usd") or 0.0)
        tx_hash = sell_res.get("tx_hash") or ""
        remaining_qty = max(0.0, initial_qty - qty_sold)

        # Calculate realized PnL %
        cost_basis_sold = qty_sold * entry_price
        realized_pnl_pct = (realized_pnl_usd / cost_basis_sold * 100.0) if cost_basis_sold > 0 else 0.0

        # Profit capture ratio: realized profit / maximum favorable excursion
        profit_capture_ratio = 0.0
        if mfe_pct > 0 and realized_pnl_pct > 0:
            profit_capture_ratio = min(1.0, round(realized_pnl_pct / mfe_pct, 4))

        # 4. Record PositionEvent
        if pct >= 99.0 or remaining_qty <= 0.0001:
            event_type = "V2_FULL_EXIT"
        elif abs(pct - 75.0) < 5.0:
            event_type = "V2_PARTIAL_EXIT_75"
        elif abs(pct - 50.0) < 5.0:
            event_type = "V2_PARTIAL_EXIT_50"
        elif abs(pct - 25.0) < 5.0:
            event_type = "V2_PARTIAL_EXIT_25"
        else:
            event_type = f"V2_PARTIAL_EXIT_{int(pct)}"

        if "HARD_STOP" in exit_reason.upper() or "SL" in exit_reason.upper():
            event_type = "V2_HARD_SL"
        elif "EMERGENCY" in exit_reason.upper():
            event_type = "V2_EMERGENCY_EXIT"
        elif "TRAILING" in exit_reason.upper():
            event_type = "V2_TRAILING_STOP"

        pos_event = PositionEvent(
            symbol=clean_sym,
            mint=clean_sym,
            mode=trade_mode,
            event_type=event_type,
            quantity=qty_sold,
            price=sell_price,
            realized_pnl_usd=round(realized_pnl_usd, 4),
            tx_hash=tx_hash,
            details={
                "exit_reason": exit_reason,
                "sell_pct": pct,
                "remaining_quantity": round(remaining_qty, 6),
                "entry_price": entry_price,
                "mfe_pct": round(mfe_pct, 2),
                "mae_pct": round(mae_pct, 2),
                "profit_capture_ratio": profit_capture_ratio,
            },
        )
        db.add(pos_event)

        # 5. Record / finalize DecisionJournal
        # Get latest closed sell trade id
        latest_trade = db.execute(
            select(Trade)
            .where(
                Trade.symbol == clean_sym,
                Trade.side == "sell",
                Trade.mode == trade_mode,
                Trade.status == "closed",
            )
            .order_by(Trade.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        trade_id = latest_trade.id if latest_trade else None

        # If fully exited or final slice sold, create complete DecisionJournal
        is_fully_closed = pct >= 99.0 or remaining_qty <= 0.0001
        if is_fully_closed:
            journal = DecisionJournal(
                trade_id=trade_id,
                symbol=clean_sym,
                mint=clean_sym,
                mode=trade_mode,
                exit_decision_id=exit_decision_id,
                exit_score=exit_score,
                initial_risk_pct=abs(ExitPolicy.DEFAULT_HARD_STOP_PCT) if hasattr(ExitPolicy, 'DEFAULT_HARD_STOP_PCT') else 12.0,
                mfe_pct=round(mfe_pct, 2),
                mae_pct=round(mae_pct, 2),
                profit_capture_ratio=profit_capture_ratio,
                final_realized_pnl_usd=round(realized_pnl_usd, 4),
                final_realized_pnl_pct=round(realized_pnl_pct, 2),
                exit_reason=exit_reason,
                ai_post_mortem=f"Trade {clean_sym} ({trade_mode}) ditutup tuntas dengan alasan '{exit_reason}'. Realized PnL: ${realized_pnl_usd:+.2f} ({realized_pnl_pct:+.1f}%). MFE: {mfe_pct:.1f}%, MAE: {mae_pct:.1f}%.",
                lessons_learned="Profit capture optimal" if profit_capture_ratio >= 0.6 else "Perlu perketat trailing stop jika retracement terlalu dalam dari MFE.",
            )
            db.add(journal)
            # Clear adaptive profit tracker state for this position
            adaptive_profit_manager.clear_position(clean_sym)

        db.commit()

        logger.info(
            f"[V2 PARTIAL EXIT] {clean_sym} ({trade_mode}) sold {pct}% ({qty_sold:.4f} units) @ ${sell_price:.6f}. "
            f"Net PnL: ${realized_pnl_usd:+.2f} ({realized_pnl_pct:+.1f}%). Event: {event_type}. Remaining: {remaining_qty:.4f}"
        )

        return {
            "status": "success",
            "symbol": clean_sym,
            "mode": trade_mode,
            "sell_pct": pct,
            "qty_sold": qty_sold,
            "remaining_quantity": remaining_qty,
            "entry_price": entry_price,
            "sell_price": sell_price,
            "realized_pnl_usd": round(realized_pnl_usd, 4),
            "realized_pnl_pct": round(realized_pnl_pct, 2),
            "mfe_pct": round(mfe_pct, 2),
            "mae_pct": round(mae_pct, 2),
            "profit_capture_ratio": profit_capture_ratio,
            "event_type": event_type,
            "exit_reason": exit_reason,
            "is_fully_closed": is_fully_closed,
            "tx_hash": tx_hash,
            "trade_id": trade_id,
        }


# Singleton
partial_exit_manager = PartialExitManager()
