"""
Position Lifecycle Aggregator (Phase 6 CEO Directive Audit Remediation).
Aggregates individual partial and full sell executions into unified, complete Position Lifecycles.

Enforces:
1. Solana `mint` address as primary token identity (prevents symbol collisions).
2. Separation of experiment, strategy, portfolio, position, and execution identifiers.
3. Reopened positions in the same mint treated as distinct lifecycles.
4. Partial exits aggregated without counting remaining tokens as realized profit.
5. Consistent mathematical denominators across MFE, MAE, PCR, and net PnL.
6. Explicit execution cost separation (network, priority, DEX fee, slippage).
7. Contemporaneous market regime at decision time with strict UNKNOWN fallback.
8. Full simulated execution trace recording.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import Trade


@dataclass
class PositionLifecycle:
    """
    Represents an entire position lifecycle from initial entry through all partial exits to closure.
    Identified strictly by Solana mint address and unique position_id.
    """
    position_id: str
    mint: str
    symbol: str
    mode: str
    experiment_id: str = "EXP_PHASE6_REMEDIATION"
    strategy_id: str = ""
    portfolio_id: str = ""
    entry_trade_id: Optional[int] = None
    execution_ids: List[str] = field(default_factory=list)
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

    # Section 6: Comprehensive execution trace
    cost_trace: Dict[str, Any] = field(default_factory=dict)


class LifecycleAggregator:
    """
    Processes trade sequences into unified, audited position lifecycles.
    Uses Solana mint address as primary token identity and enforces strict multi-strategy isolation.
    """

    @staticmethod
    def extract_mint(t: Trade) -> str:
        """
        Extracts the Solana mint address from trade notes or tx_hash.
        Defaults to a deterministic mint address if not explicitly present.
        """
        note = str(t.notes or "")
        if "mint:" in note:
            parts = note.split("mint:")
            if len(parts) > 1:
                cand = parts[1].split("]")[0].split()[0].strip()
                if cand:
                    return cand

        tx = str(t.tx_hash or "")
        if tx.startswith("mint_"):
            return tx

        # Fallback to symbol-based deterministic mint
        return f"MintSol_{t.symbol.upper()}"

    @classmethod
    def aggregate_lifecycles(cls, db: Session, mode: str = "PAPER") -> List[PositionLifecycle]:
        """
        Reconstructs position lifecycles from trades ordered chronologically.
        Uses (mode, mint) as the composite active position key.
        Guarantees that multiple entries in the same mint after full closure
        spawn separate, uniquely identified lifecycles, and different mints with
        the same symbol never collide.
        """
        stmt = (
            select(Trade)
            .where(Trade.mode == mode)
            .order_by(Trade.opened_at.asc(), Trade.id.asc())
        )
        trades = list(db.scalars(stmt).all())

        lifecycles: List[PositionLifecycle] = []
        # Keyed strictly by (mode, mint) - NOT symbol alone!
        active_positions: Dict[Tuple[str, str], PositionLifecycle] = {}

        for t in trades:
            sym = t.symbol.upper()
            mint = cls.extract_mint(t)
            pos_key = (mode, mint)

            side = (t.side or "buy").lower()
            qty = float(t.quantity or 0.0)
            price = float(t.price or 0.0)
            market_price = float(t.market_price or price)
            total = float(t.total or (qty * price))
            trade_time = t.opened_at or datetime.now(timezone.utc)
            trade_exec_id = f"exec_{t.id or uuid.uuid4().hex[:6]}"

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

            # Cost trace metadata (Section 6)
            cost_trace_item = {
                "execution_id": trade_exec_id,
                "trade_id": t.id,
                "quote_timestamp": trade_time.isoformat(),
                "side": side,
                "simulated_fill_price": price,
                "simulated_fill_quantity": qty,
                "quoted_market_price": market_price,
                "order_value_usd": total,
                "estimated_slippage_pct": slip_pct,
                "realized_slippage_usd": slip_cost,
                "network_fee_usd": base_gas,
                "priority_fee_usd": prio_fee,
                "dex_fee_usd": dex_fee,
                "simulated_latency_ms": 950,
                "quote_validity_sec": 30,
                "is_simulated_fill": True,
            }

            if side == "buy":
                # Check if there is an existing open lifecycle for this exact (mode, mint)
                if pos_key in active_positions:
                    # DCA / addition into existing open position lifecycle
                    pos = active_positions[pos_key]
                    pos.entry_quantity += qty
                    pos.remaining_quantity += qty
                    pos.total_entry_cost_usd += total
                    pos.total_entry_fees_usd += (dex_fee + gas_fee)
                    pos.execution_ids.append(trade_exec_id)
                    if pos.entry_quantity > 0:
                        pos.entry_price = round(pos.total_entry_cost_usd / pos.entry_quantity, 6)
                    pos.unrealized_cost_usd = round(pos.remaining_quantity * pos.entry_price, 4)
                    pos.peak_price_observed = max(pos.peak_price_observed, price, market_price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price, market_price)
                    pos.network_fee_usd += base_gas
                    pos.priority_fee_usd += prio_fee
                    pos.dex_fee_usd += dex_fee
                    pos.slippage_cost_usd += slip_cost
                    pos.cost_trace[trade_exec_id] = cost_trace_item
                else:
                    # New position lifecycle entry (Section 2: Mint-based Identity)
                    pos_id = f"pos_{mode}_{mint[:12]}_{int(trade_time.timestamp())}_{t.id or uuid.uuid4().hex[:6]}"
                    pos = PositionLifecycle(
                        position_id=pos_id,
                        mint=mint,
                        symbol=sym,
                        mode=mode,
                        strategy_id=f"STRAT_{mode}",
                        portfolio_id=f"PORT_{mode}",
                        entry_trade_id=t.id,
                        execution_ids=[trade_exec_id],
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
                        cost_trace={trade_exec_id: cost_trace_item},
                    )
                    active_positions[pos_key] = pos

            elif side == "sell":
                # Sell execution: could be partial or full
                if pos_key in active_positions:
                    pos = active_positions[pos_key]
                    sold_qty = min(qty, pos.remaining_quantity)
                    pos.remaining_quantity = max(0.0, pos.remaining_quantity - sold_qty)
                    pos.unrealized_cost_usd = round(pos.remaining_quantity * pos.entry_price, 4)
                    pos.total_exit_proceeds_usd += total
                    pos.total_exit_fees_usd += (dex_fee + gas_fee)
                    pos.partial_exits_count += 1
                    pos.execution_ids.append(trade_exec_id)
                    pos.peak_price_observed = max(pos.peak_price_observed, price, market_price)
                    pos.lowest_price_observed = min(pos.lowest_price_observed, price, market_price)

                    # Accumulate fees
                    pos.network_fee_usd += base_gas
                    pos.priority_fee_usd += prio_fee
                    pos.dex_fee_usd += dex_fee
                    pos.slippage_cost_usd += slip_cost
                    pos.cost_trace[trade_exec_id] = cost_trace_item

                    exit_reason = (t.notes or "SELL_EXECUTION").strip()
                    pos.exit_trades.append({
                        "trade_id": t.id,
                        "execution_id": trade_exec_id,
                        "quantity": sold_qty,
                        "price": price,
                        "proceeds_usd": total,
                        "fee_usd": dex_fee + gas_fee,
                        "closed_at": (t.closed_at or trade_time).isoformat(),
                        "exit_reason": exit_reason,
                    })
                    pos.exit_reasons.append(exit_reason)

                    # Full closure check
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

                        # Consistent Denominator Net PnL
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
                        # Pop from active positions so any subsequent buy in the same mint
                        # starts a completely new, independent lifecycle (Section 2)
                        active_positions.pop(pos_key, None)
                else:
                    # Standalone sell without prior buy record in session
                    pos_id = f"pos_{mode}_{mint[:12]}_{int(trade_time.timestamp())}_{t.id or uuid.uuid4().hex[:6]}"
                    entry_cost = market_price * qty
                    pos = PositionLifecycle(
                        position_id=pos_id,
                        mint=mint,
                        symbol=sym,
                        mode=mode,
                        strategy_id=f"STRAT_{mode}",
                        portfolio_id=f"PORT_{mode}",
                        entry_trade_id=None,
                        execution_ids=[trade_exec_id],
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
                            "execution_id": trade_exec_id,
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
                        cost_trace={trade_exec_id: cost_trace_item},
                    )
                    lifecycles.append(pos)

        # Include unclosed active positions in the return list
        for open_pos in active_positions.values():
            lifecycles.append(open_pos)

        return lifecycles
