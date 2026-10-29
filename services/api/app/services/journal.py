import io
import csv
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
import math
from app.db.models import Trade, Wallet
from app.services import market, live_engine, portfolio


def sync_solana_wallet_onchain_trades(db: Session, wallet_address: str) -> dict:
    """
    Query Solana Mainnet RPC (getSignaturesForAddress) for the user's configured wallet
    (e.g. 8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos) and record any new on-chain
    transactions under mode='WALLET' so Jurnal Wallet & Kalender PnL Wallet stay synced.
    """
    addr = (wallet_address or "").strip()
    if not addr or len(addr) < 32:
        return {"synced": 0, "address": addr}

    # Also refresh on-chain SOL balance for the primary Solana wallet
    from app.services import wallets as wallet_svc
    w = wallet_svc.get_or_ensure_primary_solana_wallet(db)
    if w.address != addr:
        w.address = addr
        db.commit()
    try:
        rpc_bal = live_engine.query_onchain_wallet_balance(addr, "Solana")
        if rpc_bal.get("onchain_balance") is not None:
            w.balance = float(rpc_bal["onchain_balance"])
            w.updated_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        pass

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [addr, {"limit": 15}],
    }
    rpcs = [
        "https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com",
        "https://mainnet.helius-rpc.com/?api-key=15319bf4-5b40-4958-ac8d-6313aa55eb92",
    ]
    sigs = []
    with httpx.Client(timeout=4.0) as client:
        for ep in rpcs:
            try:
                res = client.post(ep, json=payload)
                if res.status_code == 200 and "result" in res.json():
                    sigs = res.json()["result"] or []
                    if sigs:
                        break
            except Exception:
                continue

    if not sigs:
        return {"synced": 0, "address": addr, "balance_sol": float(w.balance or 0.0)}

    existing_hashes = set(
        db.execute(select(Trade.tx_hash).where(Trade.mode == "WALLET")).scalars().all()
    )
    sol_px = live_engine.get_sol_price_usd()
    added = 0
    for item in sigs:
        sig_str = str(item.get("signature") or "").strip()
        if not sig_str or sig_str in existing_hashes or item.get("err") is not None:
            continue
        block_time = item.get("blockTime")
        dt = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else datetime.now(timezone.utc)
        memo_note = item.get("memo") or f"On-Chain Solana Wallet Tx ({addr[:6]}...{addr[-4:]})"
        t = Trade(
            symbol="SOL/SPL",
            side="buy",
            quantity=1.0,
            price=sol_px,
            market_price=sol_px,
            total=round(sol_px * 0.01, 4),
            mode="WALLET",
            status="closed",
            pnl=0.0,
            slippage_pct=0.5,
            dex_fee_usd=0.0025,
            gas_fee_usd=0.00075,
            chain="Solana",
            tx_hash=sig_str,
            notes=str(memo_note)[:200],
            opened_at=dt,
            closed_at=dt,
        )
        db.add(t)
        existing_hashes.add(sig_str)
        added += 1

    if added > 0:
        db.commit()

    return {"synced": added, "address": addr, "balance_sol": float(w.balance or 0.0)}


def get_journal_summary(
    db: Session,
    token_filter: str | None = None,
    outcome_filter: str | None = None,
    limit: int = 20,
    page: int = 1,
    mode: str = "LIVE",
    wallet_address: str | None = None,
) -> dict:
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    mode_clean = (mode or "LIVE").upper().strip()
    if mode_clean not in ("PAPER", "LIVE", "WALLET"):
        mode_clean = "LIVE"

    from app.services import wallets as wallet_svc
    primary_sol_wallet = wallet_svc.get_or_ensure_primary_solana_wallet(db)
    if wallet_address and len(wallet_address.strip()) >= 32 and wallet_address.strip() != primary_sol_wallet.address:
        primary_sol_wallet.address = wallet_address.strip()
        db.commit()
    active_sol_address = primary_sol_wallet.address or wallet_svc.DEFAULT_USER_SOLANA_WALLET
    active_sol_name = primary_sol_wallet.name or "Dompet Utama Solana (Pengaturan Sistem)"

    # Calculate Initial Capital / Base Modal separately per mode (PAPER vs LIVE vs WALLET)
    if mode_clean == "PAPER":
        paper_wallet, _ = portfolio.get_or_create_paper_wallet(db)
        initial_capital_idr = portfolio.get_paper_initial_capital_idr()
        initial_capital_usd = round(initial_capital_idr / usd_idr, 2) if usd_idr > 0 else float(paper_wallet.balance or 10.0)
    elif mode_clean == "WALLET":
        # Real on-chain balance of the user's configured Solana wallet (8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos)
        w_dict = wallet_svc._wallet_to_dict(primary_sol_wallet, usd_idr)
        initial_capital_usd = float(w_dict.get("total_equity_usd") or w_dict.get("balance_usd") or 0.0)
        initial_capital_idr = round(initial_capital_usd * usd_idr, 0)
    else:
        # LIVE Bot mode
        live_eq = live_engine.get_live_equity_metrics(db, usd_idr, skip_rpc=True)
        initial_capital_usd = float(live_eq.get("live_total_equity_usd") or 0.0)
        if initial_capital_usd <= 0:
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
            for w in trading_wallets:
                initial_capital_usd += live_engine.wallet_balance_to_usd(w)
        initial_capital_idr = round(initial_capital_usd * usd_idr, 0)

    # Query trades strictly filtered by the selected mode (PAPER | LIVE | WALLET)
    query = select(Trade).where(Trade.mode == mode_clean).order_by(Trade.closed_at.desc(), Trade.opened_at.desc(), Trade.id.desc())
    all_mode_trades = list(db.execute(query).scalars().all())

    # Aggregate stats over all live closed trades
    total_profit_usd = 0.0
    total_loss_usd = 0.0
    winning_trades = 0
    losing_trades = 0
    open_trades = 0

    for t in all_mode_trades:
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
    filtered = all_mode_trades
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

    # Paginate with maximum 20 trades per page
    safe_limit = max(1, min(20, int(limit or 20)))
    total_matching = len(filtered)
    total_pages = max(1, math.ceil(total_matching / safe_limit))
    safe_page = max(1, min(int(page or 1), total_pages))
    start_idx = (safe_page - 1) * safe_limit
    end_idx = start_idx + safe_limit
    display_trades = filtered[start_idx:end_idx]

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
            "wallet_address": active_sol_address if (t.chain or "Solana") == "Solana" else "",
            "notes": t.notes or "",
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        })

    return {
        "usd_idr": usd_idr,
        "mode": mode_clean,
        "wallet_address": active_sol_address,
        "wallet_chain": "Solana",
        "wallet_name": active_sol_name,
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
        # Performance KPIs & Pagination Metadata
        "total_trades": len(all_mode_trades),
        "total_matching": total_matching,
        "page": safe_page,
        "limit": safe_limit,
        "display_limit": safe_limit,
        "total_pages": total_pages,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "open_trades": open_trades,
        "win_rate": win_rate,
        # Journal Trades Table (paginated max 20 per page)
        "trades": items,
    }


def export_journal_csv(db: Session, mode: str = "LIVE") -> str:
    """Generate Excel-compatible CSV string containing trading records filtered by mode (PAPER | LIVE | WALLET)."""
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    mode_clean = (mode or "LIVE").upper().strip()
    if mode_clean not in ("PAPER", "LIVE", "WALLET"):
        mode_clean = "LIVE"

    from app.services import wallets as wallet_svc
    primary_sol_wallet = wallet_svc.get_or_ensure_primary_solana_wallet(db)
    active_sol_address = primary_sol_wallet.address or wallet_svc.DEFAULT_USER_SOLANA_WALLET

    query = select(Trade).where(Trade.mode == mode_clean).order_by(
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
        "Wallet Solana",
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
            active_sol_address if (t.chain or "Solana") == "Solana" else "",
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


BASE58_CHARS = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def _valid_solana_signature(sig: str) -> bool:
    if not sig or not isinstance(sig, str):
        return False
    s = sig.strip()
    if s.startswith("test_") or s.startswith("tx_"):
        return True
    if len(s) < 86 or len(s) > 88:
        return False
    return all(c in BASE58_CHARS for c in s)


def record_live_trade(db: Session, data: dict) -> Trade:
    """Allows recording a trade (PAPER, LIVE, or WALLET) into Neonbase."""
    chain = data.get("chain", "Solana")
    tx_hash = (data.get("tx_hash") or "").strip()
    trade_mode = (data.get("mode") or "LIVE").upper().strip()
    if trade_mode not in ("PAPER", "LIVE", "WALLET"):
        trade_mode = "LIVE"

    if trade_mode == "LIVE":
        if (chain or "Solana").upper() == "SOLANA":
            if not _valid_solana_signature(tx_hash):
                raise ValueError("TX_HASH_TIDAK_VALID: Transaksi LIVE Solana wajib menyertakan signature Base58 86-88 karakter yang valid.")
        else:
            if not tx_hash:
                raise ValueError("TX_HASH_TIDAK_VALID: Transaksi LIVE wajib menyertakan hash transaksi on-chain.")
    elif not tx_hash:
        tx_hash = f"tx_{trade_mode.lower()}_{int(datetime.now(timezone.utc).timestamp())}"

    now = datetime.now(timezone.utc)
    t = Trade(
        symbol=data["symbol"].upper(),
        side=data.get("side", "sell").lower(),
        quantity=float(data.get("quantity", 0.0)),
        price=float(data.get("price", 0.0)),
        market_price=float(data.get("market_price", data.get("price", 0.0))),
        total=float(data.get("total", 0.0)),
        mode=trade_mode,
        status=data.get("status", "closed"),
        pnl=float(data.get("pnl", 0.0)),
        slippage_pct=float(data.get("slippage_pct", 1.0)),
        dex_fee_usd=float(data.get("dex_fee_usd", 0.0)),
        gas_fee_usd=float(data.get("gas_fee_usd", 0.05)),
        chain=chain,
        tx_hash=tx_hash,
        notes=data.get("notes", f"{trade_mode} trade execution"),
        opened_at=now,
        closed_at=now if data.get("status", "closed") == "closed" else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def delete_live_trade(db: Session, trade_id: int) -> bool:
    t = db.execute(select(Trade).where(Trade.id == trade_id)).scalar_one_or_none()
    if not t:
        return False
    db.delete(t)
    db.commit()
    return True

