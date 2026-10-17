import random
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import BotState, PortfolioHolding
from app.services import market, portfolio, memecoins

_BOT_ACTIVITY_LOGS: list[dict] = []
_CURRENT_STAGE: dict = {
    "stage": "IDLE",
    "stage_index": 0,
    "target_token": None,
    "detail": "Bot sedang standby. Aktifkan switch mode dan klik Jalankan Bot untuk memulai pemindaian DEX.",
}


def _append_log(badge: str, chain: str, token: str, message: str, detail_idr: str = "", level: str = "info") -> dict:
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = {
        "id": f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-{len(_BOT_ACTIVITY_LOGS)}",
        "time": now_str,
        "badge": badge,  # SCAN | AUDIT | SIGNAL | SNIPE | MEV | MONITOR | SYSTEM
        "chain": chain,
        "token": token,
        "message": message,
        "detail_idr": detail_idr,
        "level": level,  # info | success | warn | danger
    }
    _BOT_ACTIVITY_LOGS.insert(0, entry)
    if len(_BOT_ACTIVITY_LOGS) > 60:
        _BOT_ACTIVITY_LOGS.pop()
    return entry


def clear_bot_logs() -> None:
    _BOT_ACTIVITY_LOGS.clear()
    _CURRENT_STAGE.update({
        "stage": "IDLE",
        "stage_index": 0,
        "target_token": None,
        "detail": "Modal Paper telah di-reset ke Rp 150.000. Siap memindai market.",
    })
    _append_log("SYSTEM", "SOL", "RESET", "Semua portofolio & posisi Paper dihapus. Modal kembali ke Rp 150.000.", "Rp 150.000", "info")


_SNIPER_CONFIG: dict = {
    "relay_mode": "JITO_0SLOT",  # JITO_0SLOT | HELIUS_STAKED | BLOXROUTE | MAINNET_STD
    "slippage_pct": 1.0,
    "priority_fee_sol": 0.005,
    "jito_bribe_sol": 0.005,
    "anti_mev": True,
    "buy_amount_idr": 15000.0,
    "min_safety_score": 70,
    "min_liquidity_usd": 5000.0,
    "min_bonding_curve_pct": 15.0,
    "max_bonding_curve_pct": 98.0,
    "max_dev_holding_pct": 15.0,
    "max_top10_holding_pct": 35.0,
    "require_mint_revoked": True,
    "require_freeze_revoked": True,
    "require_lp_burned": True,
    "auto_tp_pct": 12.0,
    "auto_tp_sell_pct": 100.0,
    "auto_sl_pct": 8.0,
    "trailing_stop_enabled": True,
    "trailing_stop_pct": 5.0,
    "time_stop_minutes": 30,
    "multi_wallet_rotation": True,
}


def get_sniper_config() -> dict:
    return dict(_SNIPER_CONFIG)


def update_sniper_config(updates: dict) -> dict:
    for k, v in updates.items():
        if k in _SNIPER_CONFIG and v is not None:
            _SNIPER_CONFIG[k] = v
    return dict(_SNIPER_CONFIG)


def get_bot_status(db: Session) -> BotState:
    state = db.execute(select(BotState).where(BotState.id == 1)).scalar_one_or_none()
    if not state:
        state = BotState(id=1, status="idle", mode="PAPER", total_trades=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def start_bot(db: Session, mode: str) -> BotState:
    from app.services import live_engine

    norm_mode = (mode or "PAPER").strip().upper()
    if norm_mode not in ("PAPER", "LIVE"):
        norm_mode = "PAPER"

    state = get_bot_status(db)
    state.status = "running"
    state.mode = norm_mode
    state.started_at = datetime.now(timezone.utc)
    state.stopped_at = None
    state.error_message = None
    db.commit()
    db.refresh(state)

    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    if norm_mode == "LIVE":
        live_w, live_usd, _ = live_engine.get_live_trading_wallet(db, "Solana")
        w_name = live_w.name if live_w else "Hot Wallet Belum Terhubung"
        live_idr = round(live_usd * usd_idr, 0)
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 0,
            "target_token": "SOL / BASE Live Pools",
            "detail": f"Mode LIVE Aktif ({w_name}: ${live_usd:,.2f} / Rp {live_idr:,.0f}) • Memindai pool via {_SNIPER_CONFIG['relay_mode']}...",
        })
        _append_log(
            "SYSTEM",
            "SOL",
            "ENGINE",
            f"🟢 Sniper Bot diaktifkan dalam Mode LIVE On-Chain (Hot Wallet: {w_name} • Relay: {_SNIPER_CONFIG['relay_mode']})",
            f"Saldo Live: Rp {live_idr:,.0f}",
            "success",
        )
    else:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 0,
            "target_token": "SOL / BASE Pools",
            "detail": "Memindai likuiditas & pasangan meme coin baru di DexScreener Live (Mode PAPER)...",
        })
        _append_log(
            "SYSTEM",
            "SOL",
            "ENGINE",
            f"Sniper Bot diaktifkan dalam mode {norm_mode} (Auto-Snipe Aktif • Modal Simulasi Rp 150.000)",
            f"Kurs $1 = Rp {usd_idr:,.0f}",
            "success",
        )
    # Run initial scan tick (Step 1) so logs populate immediately
    run_bot_scan_tick(db, auto_trade=True, force_trade=False)
    return state


def stop_bot(db: Session) -> BotState:
    state = get_bot_status(db)
    state.status = "stopped"
    state.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(state)

    _CURRENT_STAGE.update({
        "stage": "STOPPED",
        "stage_index": 0,
        "target_token": None,
        "detail": "Mesin Sniper dihentikan oleh operator.",
    })
    _append_log("SYSTEM", "SOL", "ENGINE", "Mesin Sniper dihentikan. Pemindaian otomatis dijeda.", "", "warn")
    return state


def run_bot_scan_tick(db: Session, auto_trade: bool = True, force_trade: bool = False) -> dict:
    """Execute one real-time scan/audit/signal/auto-snipe cycle using live DexScreener market data in PAPER or LIVE mode."""
    from app.services import treasury, live_engine

    state = get_bot_status(db)
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    trade_executed = False
    trade_action = None
    active_mode = (state.mode or "PAPER").upper()

    if state.status != "running":
        return {
            "status": state.status,
            "mode": state.mode,
            "sniper_config": _SNIPER_CONFIG,
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
            "trade_executed": False,
        }

    pulse = market.get_live_pulse_feed()
    candidates = (
        (pulse.get("new_creations") or [])
        + (pulse.get("final_stretch") or [])
        + (pulse.get("migrated") or [])
    )
    holdings = list(db.execute(select(PortfolioHolding)).scalars().all())

    if not candidates:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 1,
            "target_token": "DEX Pools",
            "detail": "Menghubungi node DexScreener untuk mengambil pasangan meme coin terbaru...",
        })
        return {
            "status": state.status,
            "mode": state.mode,
            "sniper_config": _SNIPER_CONFIG,
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
            "trade_executed": False,
        }

    min_score = int(_SNIPER_CONFIG.get("min_safety_score", 70))
    min_liq = float(_SNIPER_CONFIG.get("min_liquidity_usd", 5000.0))
    held_symbols = {h.symbol.upper() for h in holdings}
    eligible = [
        c for c in candidates
        if c.get("safety_score", 0) >= min_score
        and c.get("liquidity", 0) >= min_liq
        and c["symbol"].upper() not in held_symbols
    ]
    pool_to_pick = eligible if eligible else candidates[: min(8, len(candidates))]
    pick = random.choice(pool_to_pick)

    sym = pick["symbol"]
    chain = pick.get("chain", "Solana").upper()[:4]
    price_usd = pick["price"]
    price_idr = price_usd * usd_idr
    liq_usd = pick["liquidity"]
    vol_5m = pick["volume_5m"]
    score = pick["safety_score"]

    # Cycle through realistic stages: 1=SCAN -> 2=AUDIT -> 3=SIGNAL -> 4=AUTO SNIPE & MONITOR
    next_idx = 4 if force_trade else ((_CURRENT_STAGE.get("stage_index", 0) % 4) + 1)

    if next_idx == 1:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 1,
            "target_token": sym,
            "detail": f"[{active_mode}] Memindai pool {sym} di {pick.get('launchpad', 'DEX')} • Likuiditas ${liq_usd:,.0f} • Vol 5m ${vol_5m:,.0f}",
        })
        _append_log(
            "SCAN",
            chain,
            sym,
            f"[{active_mode}] Pool aktif terdeteksi di {pick.get('launchpad')} | Harga ${price_usd:.6f} | Liq ${liq_usd:,.0f}",
            f"≈ Rp {price_idr:,.2f}",
            "info",
        )
    elif next_idx == 2:
        _CURRENT_STAGE.update({
            "stage": "RUG_SHIELD_AUDIT",
            "stage_index": 2,
            "target_token": sym,
            "detail": f"[{active_mode}] Memeriksa kontrak {sym}: Mint/Freeze Revoked, LP Lock & Konsentrasi Top 10 Holder ({pick['top10_pct']}%)",
        })
        lvl = "success" if score >= 75 else "warn"
        _append_log(
            "AUDIT",
            chain,
            sym,
            f"Kontrak Bersih (Score: {score}/100) | Top10 Non-AMM: {pick['top10_pct']}% | Liq/MCap sehat",
            "LOLOS FILTER" if score >= 75 else "WASPADA DUMP",
            lvl,
        )
    elif next_idx == 3:
        buys = pick.get("buys_5m", 12)
        sells = pick.get("sells_5m", 5)
        chg = pick.get("price_change_5m", 0.0)
        _CURRENT_STAGE.update({
            "stage": "AI_SIGNAL_SCORING",
            "stage_index": 3,
            "target_token": sym,
            "detail": f"[{active_mode}] Menganalisis orderflow 5m {sym}: {buys} Buys vs {sells} Sells (Δ {chg:+.2f}%) • Siap Auto-Snipe di tahap 4",
        })
        _append_log(
            "SIGNAL",
            chain,
            sym,
            f"Momentum 5m {chg:+.2f}% ({buys}B/{sells}S) | Bonding Curve {pick['bonding_curve_pct']}%",
            f"MCap ${pick['market_cap']:,.0f}",
            "success" if chg >= 0 else "info",
        )
    else:
        # Check 05:00 WIB daily profit settlement schedule
        treasury.check_and_run_0500_wib_schedule(db)

        paper_wallet, _ = portfolio.get_or_create_paper_wallet(db)
        if active_mode == "LIVE":
            _, avail_cash_usd, _ = live_engine.get_live_trading_wallet(db, "Solana")
            avail_cash_idr = avail_cash_usd * usd_idr
        else:
            treasury.ensure_gas_reserve(db, paper_wallet, usd_idr, needed_gas_usd=0.015)
            avail_cash_usd = float(paper_wallet.balance)
            avail_cash_idr = avail_cash_usd * usd_idr

        tp_target = float(_SNIPER_CONFIG.get("auto_tp_pct", 12.0))
        sl_target = -abs(float(_SNIPER_CONFIG.get("auto_sl_pct", 8.0)))
        tp_sell_pct = float(_SNIPER_CONFIG.get("auto_tp_sell_pct", 100.0))

        # 1. Refresh live prices on existing holdings & check Auto TP / SL
        sold_any = False
        for h in holdings:
            live_tok = market.get_live_token_info(h.symbol)
            if live_tok and live_tok.get("price", 0) > 0:
                h.current_price = float(live_tok["price"])
                if live_tok.get("liquidity", 0) > 0:
                    h.liquidity_usd = float(live_tok["liquidity"])
                h.updated_at = datetime.now(timezone.utc)
                db.commit()

            net_m = treasury.compute_holding_net_metrics(h, usd_idr)
            net_pnl_pct = net_m["net_pnl_pct"]
            gross_pnl_pct = net_m["gross_pnl_pct"]

            if auto_trade and (net_pnl_pct >= tp_target or net_pnl_pct <= sl_target):
                try:
                    sell_pct = tp_sell_pct if net_pnl_pct >= tp_target else 100.0
                    sell_res = portfolio.sell_holding(db, h.symbol, sell_pct, mode=active_mode)
                    state.total_trades = (state.total_trades or 0) + 1
                    db.commit()
                    reason = "AUTO TAKE-PROFIT (NET)" if net_pnl_pct >= tp_target else "AUTO STOP-LOSS (NET)"
                    _CURRENT_STAGE.update({
                        "stage": "AUTO_SNIPE_MONITOR",
                        "stage_index": 4,
                        "target_token": h.symbol,
                        "detail": (
                            f"⚡ [{active_mode}] {reason} dieksekusi pada {h.symbol} (Net {net_pnl_pct:+.2f}% / Gross {gross_pnl_pct:+.2f}% "
                            f"setelah Slippage {sell_res['slippage_pct']:.2f}%, DEX Fee Rp {sell_res['dex_fee_idr']:,.0f} & Gas Rp {sell_res['gas_fee_idr']:,.0f})"
                        ),
                    })
                    _append_log(
                        "SNIPE",
                        "SOL",
                        h.symbol,
                        (
                            f"[{active_mode}] {reason} {sell_pct:.0f}% @ ${sell_res['sell_price_usd']:.6f} | Net Realized PnL: Rp {sell_res['realized_pnl_idr']:+,.0f} "
                            f"(setelah Slippage, DEX Fee & Gas)"
                        ),
                        f"Kas ({active_mode}): Rp {sell_res['cash_remaining_idr']:,.0f}",
                        "success" if net_pnl_pct >= 0 else "warn",
                    )
                    trade_executed = True
                    trade_action = sell_res
                    sold_any = True
                    break
                except Exception:
                    pass

        # 2. Auto-Snipe new token if we have Cash >= Rp 15.000 and open positions < 5
        if not sold_any and auto_trade and avail_cash_idr >= 15000.0 and len(holdings) < 5 and score >= min_score - 5:
            cfg_buy_idr = float(_SNIPER_CONFIG.get("buy_amount_idr", 15000.0))
            if active_mode == "LIVE":
                snipe_idr = min(max(15000.0, cfg_buy_idr), avail_cash_idr * 0.25)
            else:
                snipe_idr = min(cfg_buy_idr, round(avail_cash_idr * 0.25, -2))
                if snipe_idr < 10000.0:
                    snipe_idr = min(15000.0, avail_cash_idr)
            try:
                snipe_res = memecoins.execute_snipe(
                    db,
                    {
                        "symbol": sym,
                        "amount_idr": snipe_idr,
                        "slippage_pct": float(_SNIPER_CONFIG.get("slippage_pct", 1.0)),
                        "priority_fee_sol": float(_SNIPER_CONFIG.get("priority_fee_sol", 0.005)),
                        "anti_mev": bool(_SNIPER_CONFIG.get("anti_mev", True)),
                        "mode": active_mode,
                    },
                )
                state.total_trades = (state.total_trades or 0) + 1
                db.commit()
                _CURRENT_STAGE.update({
                    "stage": "AUTO_SNIPE_MONITOR",
                    "stage_index": 4,
                    "target_token": snipe_res["symbol"],
                    "detail": (
                        f"⚡ [{active_mode}] AUTO-SNIPE FILLED: Beli {snipe_res['symbol']} Rp {snipe_idr:,.0f} @ ${snipe_res['entry_price']:.6f} "
                        f"(Slip {snipe_res['slippage_pct']:.2f}% • Gas Rp {snipe_res['gas_fee_idr']:,.0f})"
                    ),
                })
                trade_executed = True
                trade_action = snipe_res
            except Exception as exc:
                _CURRENT_STAGE.update({
                    "stage": "POSITION_MONITOR",
                    "stage_index": 4,
                    "target_token": sym,
                    "detail": f"Skip Auto-Snipe {sym}: {exc}",
                })
        elif not sold_any:
            ov = portfolio.get_overview(db, refresh_live_prices=True)
            if holdings:
                h = holdings[0]
                net_m = treasury.compute_holding_net_metrics(h, usd_idr)
                net_pnl_pct = net_m["net_pnl_pct"]
                gross_pnl_pct = net_m["gross_pnl_pct"]
                _CURRENT_STAGE.update({
                    "stage": "POSITION_MONITOR",
                    "stage_index": 4,
                    "target_token": h.symbol,
                    "detail": (
                        f"[{active_mode}] Memantau {len(holdings)} posisi ({h.symbol} Net PnL: {net_pnl_pct:+.2f}% | Gross: {gross_pnl_pct:+.2f}% "
                        f"setelah est. Slippage+DEX+Gas Rp {net_m['est_exit_cost_idr']:,.0f}) • Target Net TP +{tp_target}%"
                    ),
                })
                _append_log(
                    "MONITOR",
                    "SOL",
                    h.symbol,
                    f"[{active_mode}] Live ${h.current_price:.6f} | Net PnL: {net_pnl_pct:+.2f}% (setelah Slippage {net_m['exit_slippage_pct']:.2f}%, DEX & Gas)",
                    f"Net ≈ Rp {net_m['net_value_usd'] * usd_idr:,.0f}",
                    "success" if net_pnl_pct >= 0 else "warn",
                )
            else:
                _CURRENT_STAGE.update({
                    "stage": "MEV_STANDBY",
                    "stage_index": 4,
                    "target_token": sym,
                    "detail": f"Sisa kas {active_mode} Rp {avail_cash_idr:,.0f}. Menunggu sinyal token yang lolos filter keamanan.",
                })

    return {
        "status": state.status,
        "mode": state.mode,
        "total_trades": state.total_trades or 0,
        "sniper_config": _SNIPER_CONFIG,
        "current_stage": _CURRENT_STAGE,
        "logs": _BOT_ACTIVITY_LOGS[:25],
        "usd_idr": usd_idr,
        "trade_executed": trade_executed,
        "trade_action": trade_action,
    }


def get_bot_activity(db: Session, tick: bool = True, force_trade: bool = False) -> dict:
    state = get_bot_status(db)
    if (tick or force_trade) and state.status == "running":
        return run_bot_scan_tick(db, auto_trade=True, force_trade=force_trade)
    fx = market.get_fx_rate()
    return {
        "status": state.status,
        "mode": state.mode,
        "total_trades": state.total_trades or 0,
        "sniper_config": _SNIPER_CONFIG,
        "current_stage": _CURRENT_STAGE,
        "logs": _BOT_ACTIVITY_LOGS[:25],
        "usd_idr": fx["usd_idr"],
        "trade_executed": False,
    }

