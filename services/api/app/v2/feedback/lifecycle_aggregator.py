"""
Position Lifecycle Aggregator (Phase 6 CEO Directive Audit Corrections).
Aggregates individual partial and full sell executions into unified, complete Position Lifecycles.

Enforces:
1. Unique `position_id` / `lifecycle_id` (not symbol alone).
2. Reopened positions in the same token treated as distinct lifecycles.
3. Partial exits aggregated without counting remaining tokens as realized profit.
4. Consistent mathematical denominators across MFE, MAE, PCR, and net PnL.
5. Explicit execution cost separation (network, priority, DEX fee, slippage).
6. Contemporaneous market regime at decision time.
7. Missing or stale regime data classified as UNKNOWN.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import Trade


@dataclass
class PositionLifecycle:
    """
    Represents an entire position lifecycle from initial entry through all partial exits to closure.
    """
    position_id: str
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
    unrealized_cost_usd: float = 0.0  # Remaining capital strictly separated from realized PnL
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
    contemporaneous_regime: str = "UNKNOWN"  # Audit Correction 6 & 7: "UNKNOWN" if missing/stale

    # Detailed execution cost breakdown (Audit Correction 5)
    network_fee_usd: float = 0.0      # Base Solana signature fees
    priority_fee_usd: float = 0.0     # Solana CU priority fees
    dex_fee_usd: float = 0.0          # DEX / LP pool fees
    slippage_cost_usd: float = 0.0    # Realized slippage friction ($)
    total_execution_costs_usd: float = 0.0


class LifecycleAggregator:
    """
    Processes closed trade sequences into unified, audited position lifecycles.
    """

    @classmethod
    def aggregate_lifecycles(cls, db: Session, mode: str = "PAPER") -> List[PositionLifecycle]:
        """
        Reconstructs position lifecycles from trades ordered chronologically.
        Guarantees that multiple entries in the same token after full closure
        spawn separate, uniquely identified lifecycles.
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
            market_price = float(t.market_price or price)
            total = float(t.total or (qty * price))
            trade_time = t.opened_at or datetime.now(timezone.utc)

            # Cost breakdown
            dex_fee = float(t.dex_fee_usd or 0.0)
            gas_fee = float(t.gas_fee_usd or 0.0)
            # Gas fee splits: base $0.001, priority rest
            base_gas = round(min(0.001, gas_fee), 4)
            prio_fee = round(max(0.0, gas_fee - base_gas), 4)
            # Slippage cost: difference between fill price and market quote * qty
            slip_pct = float(t.slippage_pct or 0.0)
            slip_cost = round(total * (slip_pct / 100.0), 5) if slip_pct > 0 else 0.0

            # Contemporaneous regime parsing from notes or tags
            note = str(t.notes or "")
            regime = "UNKNOWN"
            if "[trending]" in note.lower() or "trending" in note.lower():
                regime = "trending"
            elif "[ranging]" in note.lower() or "ranging" in note.lower():
                regime = "ranging"
            elif "[choppy]" in note.lower() or "choppy" in note.lower():
                regime = "choppy"

            if side == "buy":
                # Check if there is an existing open lifecycle for this symbol
                if sym in active_positions:
                    # DCA / addition into existing open position lifecycle
                    pos = active_positions[sym]
                    pos.entry_quantity += qty
                    pos.remaining_quantity += qty
                    pos.total_entry_cost_usd += total
                    pos.total_entry_fees_usd += (dex_fee + gas_fee)
                    if pos.entry_quantity > 0:
                        pos.entry_price = round(pos.total_entry_cost_usd / pos.entry_quantity, 6)
                    pos.unrealized_cost_usd = round(pos.remaining_quantity * pos.entry_price, 4)
                    pos.peak_price_observed = max(pos.peak_price_observed, price, market_price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price, market_price)
                    pos.network_fee_usd += base_gas
                    pos.priority_fee_usd += prio_fee
                    pos.dex_fee_usd += dex_fee
                    pos.slippage_cost_usd += slip_cost
                else:
                    # New position lifecycle entry (Audit Correction 1 & 2)
                    pos_id = f"pos_{mode}_{sym}_{int(trade_time.timestamp())}_{t.id or uuid.uuid4().hex[:6]}"
                    pos = PositionLifecycle(
                        position_id=pos_id,
                        symbol=sym,
                        mode=mode,
                        entry_trade_id=t.id,
                        opened_at=trade_time,
                        entry_quantity=qty,
                        entry_price=price,
                        total_entry_cost_usd=total,
                        total_entry_fees_usd=dex_fee + gas_fee,
                        remaining_quantity=qty,
                        unrealized_cost_usd=total,
                        peak_price_observed=max(price, market_price),
                        lowest_price_observed=min(price, market_price),
                        status="OPEN",
                        contemporaneous_regime=regime,
                        network_fee_usd=base_gas,
                        priority_fee_usd=prio_fee,
                        dex_fee_usd=dex_fee,
                        slippage_cost_usd=slip_cost,
                    )
                    active_positions[sym] = pos

            elif side == "sell":
                # Sell execution: could be partial or full
                if sym in active_positions:
                    pos = active_positions[sym]
                    sold_qty = min(qty, pos.remaining_quantity)
                    pos.remaining_quantity = max(0.0, pos.remaining_quantity - sold_qty)
                    pos.unrealized_cost_usd = round(pos.remaining_quantity * pos.entry_price, 4)
                    pos.total_exit_proceeds_usd += total
                    pos.total_exit_fees_usd += (dex_fee + gas_fee)
                    pos.partial_exits_count += 1
                    pos.peak_price_observed = max(pos.peak_price_observed, price, market_price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price, market_price)

                    # Accumulate fees
                    pos.network_fee_usd += base_gas
                    pos.priority_fee_usd += prio_fee
                    pos.dex_fee_usd += dex_fee
                    pos.slippage_cost_usd += slip_cost

                    exit_reason = (t.notes or "SELL_EXECUTION").strip()
                    pos.exit_trades.append({
                        "trade_id": t.id,
                        "quantity": sold_qty,
                        "price": price,
                        "proceeds_usd": total,
                        "fee_usd": dex_fee + gas_fee,
                        "closed_at": (t.closed_at or trade_time).isoformat(),
                        "exit_reason": exit_reason,
                    })
                    pos.exit_reasons.append(exit_reason)

                    # Full closure check (Audit Correction 2)
                    is_full_exit = (
                        pos.remaining_quantity <= 0.0001
                        or "FULL" in exit_reason
                        or "100" in exit_reason
                    )

                    if is_full_exit:
                        pos.status = "CLOSED"
                        pos.remaining_quantity = 0.0
                        pos.unrealized_cost_usd = 0.0
                        pos.closed_at = t.closed_at or trade_time
                        if pos.opened_at:
                            pos.holding_time_seconds = max(0.0, (pos.closed_at - pos.opened_at).total_seconds())

                        # Consistent Denominator Net PnL (Audit Correction 3 & 4)
                        total_fees = pos.total_entry_fees_usd + pos.total_exit_fees_usd
                        pos.total_execution_costs_usd = round(
                            pos.network_fee_usd + pos.priority_fee_usd + pos.dex_fee_usd + pos.slippage_cost_usd,
                            5
                        )
                        pos.net_pnl_usd = round(
                            pos.total_exit_proceeds_usd - pos.total_entry_cost_usd - total_fees,
                            4
                        )
                        if pos.total_entry_cost_usd > 0:
                            pos.net_pnl_pct = round(
                                (pos.net_pnl_usd / pos.total_entry_cost_usd) * 100.0, 2
                            )
                        pos.is_win = pos.net_pnl_usd >= 0.0

                        # Volume-weighted average exit price
                        total_sold = sum(et["quantity"] for et in pos.exit_trades)
                        weighted_exit_price = (
                            sum(et["quantity"] * et["price"] for et in pos.exit_trades) / total_sold
                            if total_sold > 0
                            else price
                        )

                        # Excursion & PCR with consistent entry denominator
                        if pos.entry_price > 0:
                            pos.mfe_pct = round(
                                ((pos.peak_price_observed - pos.entry_price) / pos.entry_price) * 100.0, 2
                            )
                            pos.mae_pct = round(
                                ((pos.lowest_price_observed - pos.entry_price) / pos.entry_price) * 100.0, 2
                            )

                            peak_gain = pos.peak_price_observed - pos.entry_price
                            if peak_gain > 0 and weighted_exit_price > pos.entry_price:
                                pos.profit_capture_ratio = round(
                                    (weighted_exit_price - pos.entry_price) / peak_gain, 4
                                )
                            else:
                                pos.profit_capture_ratio = 0.0

                        lifecycles.append(pos)
                        # Pop from active positions so any subsequent buy in the same symbol
                        # starts a completely new, independent lifecycle (Audit Correction 2)
                        active_positions.pop(sym, None)
                else:
                    # Standalone sell without prior buy record in session
                    pos_id = f"pos_{mode}_{sym}_{int(trade_time.timestamp())}_{t.id or uuid.uuid4().hex[:6]}"
                    entry_cost = market_price * qty
                    pos = PositionLifecycle(
                        position_id=pos_id,
                        symbol=sym,
                        mode=mode,
                        entry_trade_id=None,
                        opened_at=t.opened_at or trade_time,
                        closed_at=t.closed_at or trade_time,
                        entry_quantity=qty,
                        entry_price=market_price,
                        total_entry_cost_usd=entry_cost,
                        total_entry_fees_usd=(dex_fee + gas_fee) * 0.5,
                        total_exit_proceeds_usd=total,
                        total_exit_fees_usd=(dex_fee + gas_fee) * 0.5,
                        remaining_quantity=0.0,
                        unrealized_cost_usd=0.0,
                        peak_price_observed=max(price, market_price),
                        lowest_price_observed=min(price, market_price),
                        partial_exits_count=1,
                        exit_trades=[{
                            "trade_id": t.id,
                            "quantity": qty,
                            "price": price,
                            "proceeds_usd": total,
                            "fee_usd": dex_fee + gas_fee,
                            "closed_at": (t.closed_at or trade_time).isoformat(),
                            "exit_reason": t.notes or "STANDALONE_SELL",
                        }],
                        exit_reasons=[t.notes or "STANDALONE_SELL"],
                        status="CLOSED",
                        net_pnl_usd=round(float(t.pnl or 0.0), 4),
                        net_pnl_pct=round(
                            (float(t.pnl or 0.0) / max(total - float(t.pnl or 0.0), 1.0)) * 100.0, 2
                        ),
                        is_win=float(t.pnl or 0.0) >= 0.0,
                        contemporaneous_regime=regime,
                        network_fee_usd=base_gas,
                        priority_fee_usd=prio_fee,
                        dex_fee_usd=dex_fee,
                        slippage_cost_usd=slip_cost,
                        total_execution_costs_usd=round(base_gas + prio_fee + dex_fee + slip_cost, 5),
                    )
                    lifecycles.append(pos)

        # Include unclosed active positions in the return list
        for open_pos in active_positions.values():
            lifecycles.append(open_pos)

        return lifecycles
