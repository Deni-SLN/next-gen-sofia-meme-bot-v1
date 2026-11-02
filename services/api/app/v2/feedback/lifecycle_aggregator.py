"""
Position Lifecycle Aggregator (Phase 6 Pre-Validation Correction 2 & 3).
Aggregates individual partial and full sell executions into unified, complete Position Lifecycles.
Ensures Winrate, Profit Factor, Expectancy, and Profit Capture Ratio are computed from
completed position lifecycles rather than isolated fractional trade events.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.db.models import Trade


@dataclass
class PositionLifecycle:
    """
    Represents an entire position lifecycle from initial entry through all partial exits to closure.
    """
    symbol: str
    mode: str
    entry_trade_id: Optional[int] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    entry_quantity: float = 0.0
    entry_price: float = 0.0
    total_entry_cost_usd: float = 0.0
    total_entry_fees_usd: float = 0.0
    total_exit_proceeds_usd: float = 0.0
    total_exit_fees_usd: float = 0.0
    remaining_quantity: float = 0.0
    peak_price_observed: float = 0.0
    lowest_price_observed: float = 0.0
    partial_exits_count: int = 0
    exit_trades: List[Dict[str, Any]] = field(default_factory=list)
    exit_reasons: List[str] = field(default_factory=list)
    status: str = "OPEN"  # OPEN, CLOSED
    net_pnl_usd: float = 0.0
    net_pnl_pct: float = 0.0
    profit_capture_ratio: float = 0.0
    holding_time_seconds: float = 0.0
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    is_win: bool = False
    contemporaneous_regime: str = "ranging"  # Contemporaneous market regime at entry (Correction 4)


class LifecycleAggregator:
    """
    Processes closed trade sequences into unified position lifecycles.
    """

    @classmethod
    def aggregate_lifecycles(cls, db: Session, mode: str = "PAPER") -> List[PositionLifecycle]:
        """
        Reconstructs position lifecycles from trades ordered chronologically.
        Matches entry BUYs with subsequent partial and full SELLs.
        """
        stmt = (
            select(Trade)
            .where(Trade.mode == mode)
            .order_by(Trade.opened_at.asc(), Trade.id.asc())
        )
        trades = list(db.scalars(stmt).all())

        lifecycles: List[PositionLifecycle] = []
        active_positions: Dict[str, PositionLifecycle] = {}

        for t in trades:
            sym = t.symbol.upper()
            side = (t.side or "buy").lower()
            qty = float(t.quantity or 0.0)
            price = float(t.price or 0.0)
            total = float(t.total or (qty * price))
            fee = float(t.dex_fee_usd or 0.0) + float(t.gas_fee_usd or 0.0)
            trade_time = t.opened_at or datetime.now(timezone.utc)

            if side == "buy":
                # Check if there is an existing open lifecycle for this symbol
                if sym in active_positions:
                    # Additional buy / DCA into position
                    pos = active_positions[sym]
                    old_cost = pos.total_entry_cost_usd
                    pos.entry_quantity += qty
                    pos.remaining_quantity += qty
                    pos.total_entry_cost_usd += total
                    pos.total_entry_fees_usd += fee
                    if pos.entry_quantity > 0:
                        pos.entry_price = round(pos.total_entry_cost_usd / pos.entry_quantity, 6)
                    pos.peak_price_observed = max(pos.peak_price_observed, price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price)
                else:
                    # New position lifecycle entry
                    pos = PositionLifecycle(
                        symbol=sym,
                        mode=mode,
                        entry_trade_id=t.id,
                        opened_at=trade_time,
                        entry_quantity=qty,
                        entry_price=price,
                        total_entry_cost_usd=total,
                        total_entry_fees_usd=fee,
                        remaining_quantity=qty,
                        peak_price_observed=price,
                        lowest_price_observed=price,
                        status="OPEN",
                        contemporaneous_regime="ranging",
                    )
                    active_positions[sym] = pos

            elif side == "sell":
                # Sell execution: could be partial or full
                if sym in active_positions:
                    pos = active_positions[sym]
                    sold_qty = min(qty, pos.remaining_quantity)
                    pos.remaining_quantity = max(0.0, pos.remaining_quantity - sold_qty)
                    pos.total_exit_proceeds_usd += total
                    pos.total_exit_fees_usd += fee
                    pos.partial_exits_count += 1
                    pos.peak_price_observed = max(pos.peak_price_observed, price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price)

                    exit_reason = (t.notes or "SELL_EXECUTION").strip()
                    pos.exit_trades.append({
                        "trade_id": t.id,
                        "quantity": sold_qty,
                        "price": price,
                        "proceeds_usd": total,
                        "fee_usd": fee,
                        "closed_at": (t.closed_at or trade_time).isoformat(),
                        "exit_reason": exit_reason,
                    })
                    pos.exit_reasons.append(exit_reason)

                    # Check if position is fully closed (zero remaining tokens or explicit full exit)
                    is_full_exit = (pos.remaining_quantity <= 0.0001) or ("FULL" in exit_reason) or ("100" in exit_reason)
                    if is_full_exit:
                        pos.status = "CLOSED"
                        pos.remaining_quantity = 0.0
                        pos.closed_at = t.closed_at or trade_time
                        if pos.opened_at:
                            pos.holding_time_seconds = max(0.0, (pos.closed_at - pos.opened_at).total_seconds())

                        # Net PnL = Total Exit Proceeds - Total Entry Cost - Total Fees
                        total_fees = pos.total_entry_fees_usd + pos.total_exit_fees_usd
                        pos.net_pnl_usd = round(pos.total_exit_proceeds_usd - pos.total_entry_cost_usd - total_fees, 4)
                        if pos.total_entry_cost_usd > 0:
                            pos.net_pnl_pct = round((pos.net_pnl_usd / pos.total_entry_cost_usd) * 100.0, 2)
                        pos.is_win = pos.net_pnl_usd >= 0.0

                        # Calculate volume-weighted exit price
                        total_sold = sum(et["quantity"] for et in pos.exit_trades)
                        weighted_exit_price = (
                            sum(et["quantity"] * et["price"] for et in pos.exit_trades) / total_sold
                            if total_sold > 0
                            else price
                        )

                        # MFE and MAE calculation
                        if pos.entry_price > 0:
                            pos.mfe_pct = round(((pos.peak_price_observed - pos.entry_price) / pos.entry_price) * 100.0, 2)
                            pos.mae_pct = round(((pos.lowest_price_observed - pos.entry_price) / pos.entry_price) * 100.0, 2)

                            # Profit Capture Ratio: (WeightedExit - Entry) / (Peak - Entry)
                            peak_gain = pos.peak_price_observed - pos.entry_price
                            if peak_gain > 0 and weighted_exit_price > pos.entry_price:
                                pos.profit_capture_ratio = round((weighted_exit_price - pos.entry_price) / peak_gain, 4)
                            else:
                                pos.profit_capture_ratio = 0.0

                        lifecycles.append(pos)
                        del active_positions[sym]
                else:
                    # Standalone sell without tracked entry (e.g. legacy or simulated trade)
                    pos = PositionLifecycle(
                        symbol=sym,
                        mode=mode,
                        entry_trade_id=None,
                        opened_at=t.opened_at or trade_time,
                        closed_at=t.closed_at or trade_time,
                        entry_quantity=qty,
                        entry_price=float(t.market_price or price),
                        total_entry_cost_usd=float(t.market_price or price) * qty,
                        total_entry_fees_usd=fee * 0.5,
                        total_exit_proceeds_usd=total,
                        total_exit_fees_usd=fee * 0.5,
                        remaining_quantity=0.0,
                        peak_price_observed=max(price, float(t.market_price or price)),
                        lowest_price_observed=min(price, float(t.market_price or price)),
                        partial_exits_count=1,
                        exit_trades=[{
                            "trade_id": t.id,
                            "quantity": qty,
                            "price": price,
                            "proceeds_usd": total,
                            "fee_usd": fee,
                            "closed_at": (t.closed_at or trade_time).isoformat(),
                            "exit_reason": t.notes or "STANDALONE_SELL",
                        }],
                        exit_reasons=[t.notes or "STANDALONE_SELL"],
                        status="CLOSED",
                        net_pnl_usd=round(float(t.pnl or 0.0), 4),
                        net_pnl_pct=round((float(t.pnl or 0.0) / max(total - float(t.pnl or 0.0), 1.0)) * 100.0, 2),
                        is_win=float(t.pnl or 0.0) >= 0.0,
                    )
                    lifecycles.append(pos)

        return lifecycles
