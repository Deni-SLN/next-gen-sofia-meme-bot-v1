import io
import csv
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Trade, Wallet
from app.services import market


def get_journal_summary(
    db: Session,
    token_filter: str | None = None,
    outcome_filter: str | None = None,
    limit: int = 10,
) -> dict:
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    # Calculate Modal Awal Live Trading from hot wallets (trading gate)
    trading_wallets = list(
        db.execute(
            select(Wallet).where(
                Wallet.gate == "trading",
                ~Wallet.name.contains("Modal Paper"),
            )
        )
        .scalars()
        .all()
    )

    initial_capital_usd = 0.0
    for w in trading_wallets:
        token_upper = (w.token or "USDT").upper()
        if "SOL" in token_upper and "USD" not in token_upper:
            sol_info = market.get_live_token_info("SOL/USDT")
            sol_price = float(sol_info["price"]) if (sol_info and sol_info.get("price", 0) > 10) else 145.0
            initial_capital_usd += float(w.balance) * sol_price
        else:
            initial_capital_usd += float(w.balance)

    initial_capital_idr = round(initial_capital_usd * usd_idr, 0)

    # Query all LIVE trades stored in Neonbase
    query = select(Trade).where(Trade.mode == "LIVE").order_by(Trade.closed_at.desc(), Trade.opened_at.desc(), Trade.id.desc())
    all_live_trades = list(db.execute(query).scalars().all())

    # Aggregate stats over all live closed trades
    total_profit_usd = 0.0
    total_loss_usd = 0.0
    winning_trades = 0
    losing_trades = 0
    open_trades = 0

    for t in all_live_trades:
        pnl_val = float(t.pnl or 0.0)
        if t.status == "open":
            open_trades += 1
        elif pnl_val > 0:
            total_profit_usd += pnl_val
            winning_trades += 1
        elif pnl_val < 0:
            total_loss_usd += abs(pnl_val)
            losing_trades += 1

    total_profit_usd = round(total_profit_usd, 4)
    total_loss_usd = round(total_loss_usd, 4)
    net_result_usd = round(total_profit_usd - total_loss_usd, 4)

    total_profit_idr = round(total_profit_usd * usd_idr, 0)
    total_loss_idr = round(total_loss_usd * usd_idr, 0)
    net_result_idr = round(net_result_usd * usd_idr, 0)

    net_result_pct = round((net_result_usd / initial_capital_usd * 100.0), 2) if initial_capital_usd > 0 else 0.0
    total_closed = winning_trades + losing_trades
    win_rate = round((winning_trades / total_closed * 100.0), 1) if total_closed > 0 else 0.0

    # Filter trades if search or outcome filter specified
    filtered = all_live_trades
    if token_filter and token_filter.strip():
        tf = token_filter.strip().upper()
        filtered = [t for t in filtered if tf in (t.symbol or "").upper() or tf in (t.chain or "").upper()]

    if outcome_filter:
        of = outcome_filter.strip().upper()
        if of == "WIN":
            filtered = [t for t in filtered if (t.pnl or 0) > 0 and t.status != "open"]
        elif of == "LOSS":
            filtered = [t for t in filtered if (t.pnl or 0) < 0 and t.status != "open"]
        elif of == "OPEN":
            filtered = [t for t in filtered if t.status == "open"]

    # Slice to 10 latest transactions by default so Neonbase payload and UI rendering are lightweight
    total_matching = len(filtered)
    display_trades = filtered[:limit] if limit > 0 else filtered

    items = []
    for t in display_trades:
        pnl_val = float(t.pnl or 0.0)
        qty = float(t.quantity or 0.0)
        px = float(t.price or 0.0)
        tot = float(t.total or (qty * px))
        dex_fee = float(t.dex_fee_usd or 0.0)
        gas_fee = float(t.gas_fee_usd or 0.0)
        tot_fees = dex_fee + gas_fee

        if t.status == "open":
            res_label = "OPEN"
        elif pnl_val > 0:
            res_label = "WIN"
        elif pnl_val < 0:
            res_label = "LOSS"
        else:
            res_label = "BE"

        cost_basis = tot - pnl_val if (tot > pnl_val and pnl_val != 0) else tot
        pnl_pct = round((pnl_val / cost_basis * 100.0), 2) if cost_basis > 0 else 0.0

        items.append({
            "id": t.id,
            "symbol": t.symbol,
            "chain": t.chain or "Solana",
            "side": t.side,
            "quantity": qty,
            "price": px,
            "price_idr": round(px * usd_idr, 2),
            "market_price": float(t.market_price or px),
            "market_price_idr": round(float(t.market_price or px) * usd_idr, 2),
            "total_usd": round(tot, 4),
            "total_idr": round(tot * usd_idr, 0),
            "slippage_pct": round(float(t.slippage_pct or 0.0), 2),
            "dex_fee_usd": round(dex_fee, 4),
            "dex_fee_idr": round(dex_fee * usd_idr, 0),
            "gas_fee_usd": round(gas_fee, 4),
            "gas_fee_idr": round(gas_fee * usd_idr, 0),
            "total_fees_usd": round(tot_fees, 4),
            "total_fees_idr": round(tot_fees * usd_idr, 0),
            "pnl_usd": round(pnl_val, 4),
            "pnl_idr": round(pnl_val * usd_idr, 0),
            "pnl_pct": pnl_pct,
            "status": t.status,
            "result": res_label,
            "tx_hash": t.tx_hash or "",
            "notes": t.notes or "",
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        })

    return {
        "usd_idr": usd_idr,
        "mode": "LIVE",
        # 4 Core Cards requested by user
        "initial_capital_usd": round(initial_capital_usd, 2),
        "initial_capital_idr": initial_capital_idr,
        "total_profit_usd": total_profit_usd,
        "total_profit_idr": total_profit_idr,
        "total_loss_usd": total_loss_usd,
        "total_loss_idr": total_loss_idr,
        "net_result_usd": net_result_usd,
        "net_result_idr": net_result_idr,
        "net_result_pct": net_result_pct,
        # Performance KPIs
        "total_trades": len(all_live_trades),
        "total_matching": total_matching,
        "display_limit": limit,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "open_trades": open_trades,
        "win_rate": win_rate,
        # Live Journal Trades Table (10 latest)
        "trades": items,
    }


def export_journal_csv(db: Session) -> str:
    """Generate Excel-compatible CSV string containing all live trading records from Neonbase."""
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    query = select(Trade).where(Trade.mode == "LIVE").order_by(
        Trade.closed_at.desc().nullslast(),
        Trade.opened_at.desc().nullslast(),
        Trade.id.desc(),
    )
    all_live_trades = list(db.execute(query).scalars().all())

    output = io.StringIO()
    # UTF-8 BOM ensures Microsoft Excel on Windows reads UTF-8 characters and currency signs without garbled text
    output.write("\ufeff")

    writer = csv.writer(output)
    writer.writerow([
        "ID Transaksi",
        "Waktu Buka",
        "Waktu Tutup",
        "Koin / Token",
        "Network / Chain",
        "Posisi",
        "Jumlah (Qty)",
        "Harga Eksekusi ($)",
        "Harga Eksekusi (Rp)",
        "Total Nilai ($)",
        "Total Nilai (Rp)",
        "Biaya Gas ($)",
        "Biaya DEX ($)",
        "Total Biaya ($)",
        "Total Biaya (Rp)",
        "Slippage (%)",
        "Keuntungan / Kerugian ($)",
        "Keuntungan / Kerugian (Rp)",
        "Hasil (WIN/LOSS/OPEN)",
        "Status",
        "Tx Hash Explorer",
        "Catatan Bot",
    ])

    for t in all_live_trades:
        pnl_val = float(t.pnl or 0.0)
        qty = float(t.quantity or 0.0)
        px = float(t.price or 0.0)
        tot = float(t.total or (qty * px))
        dex_fee = float(t.dex_fee_usd or 0.0)
        gas_fee = float(t.gas_fee_usd or 0.0)
        tot_fee = dex_fee + gas_fee

        if t.status == "open":
            res_label = "OPEN"
        elif pnl_val > 0:
            res_label = "WIN"
        elif pnl_val < 0:
            res_label = "LOSS"
        else:
            res_label = "BE"

        writer.writerow([
            t.id,
            t.opened_at.strftime("%Y-%m-%d %H:%M:%S") if t.opened_at else "",
            t.closed_at.strftime("%Y-%m-%d %H:%M:%S") if t.closed_at else "",
            t.symbol,
            t.chain or "Solana",
            (t.side or "sell").upper(),
            qty,
            f"{px:.8f}".rstrip("0").rstrip(".") if px < 1 else f"{px:.4f}",
            round(px * usd_idr, 2),
            round(tot, 4),
            round(tot * usd_idr, 0),
            round(gas_fee, 4),
            round(dex_fee, 4),
            round(tot_fee, 4),
            round(tot_fee * usd_idr, 0),
            round(float(t.slippage_pct or 0.0), 2),
            round(pnl_val, 4),
            round(pnl_val * usd_idr, 0),
            res_label,
            t.status,
            t.tx_hash or "",
            t.notes or "Bot live execution",
        ])

    return output.getvalue()


def record_live_trade(db: Session, data: dict) -> Trade:
    """Allows recording a live bot trade or manual on-chain execution into Neonbase."""
    now = datetime.now(timezone.utc)
    t = Trade(
        symbol=data["symbol"].upper(),
        side=data.get("side", "sell").lower(),
        quantity=float(data.get("quantity", 0.0)),
        price=float(data.get("price", 0.0)),
        market_price=float(data.get("market_price", data.get("price", 0.0))),
        total=float(data.get("total", 0.0)),
        mode="LIVE",
        status=data.get("status", "closed"),
        pnl=float(data.get("pnl", 0.0)),
        slippage_pct=float(data.get("slippage_pct", 1.0)),
        dex_fee_usd=float(data.get("dex_fee_usd", 0.0)),
        gas_fee_usd=float(data.get("gas_fee_usd", 0.05)),
        chain=data.get("chain", "Solana"),
        tx_hash=data.get("tx_hash", ""),
        notes=data.get("notes", "Bot live execution"),
        opened_at=now,
        closed_at=now if data.get("status", "closed") == "closed" else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def delete_live_trade(db: Session, trade_id: int) -> bool:
    t = db.execute(select(Trade).where(Trade.id == trade_id, Trade.mode == "LIVE")).scalar_one_or_none()
    if not t:
        return False
    db.delete(t)
    db.commit()
    return True

