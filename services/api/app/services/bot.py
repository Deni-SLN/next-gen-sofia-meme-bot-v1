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


STRATEGY_PRESETS: dict[str, dict] = {
    "SAFE": {
        "strategy_mode": "SAFE",
        "strategy_label": "🛡️ SAFE (Konservatif • Token Lulus & Likuiditas Tinggi)",
        "strategy_desc": "Hanya membeli token yang sudah Migrated (Raydium/PumpSwap) dengan likuiditas > $20K & Safety Score ≥ 82.",
        "relay_mode": "JITO_0SLOT",
        "slippage_pct": 0.8,
        "priority_fee_sol": 0.003,
        "jito_bribe_sol": 0.003,
        "buy_amount_idr": 15000.0,
        "min_safety_score": 82,
        "min_liquidity_usd": 20000.0,
        "min_bonding_curve_pct": 85.0,
        "max_dev_holding_pct": 5.0,
        "only_new_creations": False,
        "max_token_age_minutes": 999999,
        "max_market_cap_usd": 999999999.0,
        "min_5m_buys": 8,
        "discovery_sources": ["DexScreener Migrated Pools", "Raydium / PumpSwap Verified"],
        "auto_tp_pct": 15.0,
        "auto_sl_pct": 6.0,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 4.0,
        "time_stop_minutes": 45,
        "max_open_positions": 3,
        "tick_interval_ms": 4000,
    },
    "DEFAULT": {
        "strategy_mode": "DEFAULT",
        "strategy_label": "⚖️ DEFAULT (Seimbang • Final Stretch & Migrated)",
        "strategy_desc": "Seimbang antara keamanan kontrak (Score ≥ 70) dan momentum orderflow pada pool Final Stretch & Migrated.",
        "relay_mode": "JITO_0SLOT",
        "slippage_pct": 1.2,
        "priority_fee_sol": 0.005,
        "jito_bribe_sol": 0.005,
        "buy_amount_idr": 20000.0,
        "min_safety_score": 70,
        "min_liquidity_usd": 5000.0,
        "min_bonding_curve_pct": 25.0,
        "max_dev_holding_pct": 10.0,
        "only_new_creations": False,
        "max_token_age_minutes": 2880,
        "max_market_cap_usd": 50000000.0,
        "min_5m_buys": 5,
        "discovery_sources": ["DexScreener Final Stretch", "GMGN.ai Momentum"],
        "auto_tp_pct": 25.0,
        "auto_sl_pct": 8.0,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 5.0,
        "time_stop_minutes": 30,
        "max_open_positions": 5,
        "tick_interval_ms": 3000,
    },
    "AGGRESSIVE": {
        "strategy_mode": "AGGRESSIVE",
        "strategy_label": "🔥 AGRESIF (DexScreener + GMGN.ai New Meme Sniper • Koin Baru & Cepat)",
        "strategy_desc": "Khusus menyergap meme coin BARU MUNCUL (New Creations < 3 Jam, MCap < $500K) via DexScreener Token Profiles v1 & GMGN.ai Trench Radar. Memblokir 100% koin lama seperti BONK/PEPE/WIF.",
        "relay_mode": "JITO_0SLOT",
        "slippage_pct": 2.5,
        "priority_fee_sol": 0.008,
        "jito_bribe_sol": 0.008,
        "buy_amount_idr": 25000.0,
        "min_safety_score": 55,
        "min_liquidity_usd": 1500.0,
        "min_bonding_curve_pct": 10.0,
        "max_dev_holding_pct": 18.0,
        "only_new_creations": True,
        "max_token_age_minutes": 180,
        "max_market_cap_usd": 500000.0,
        "min_5m_buys": 2,
        "discovery_sources": [
            "DexScreener Token Profiles v1",
            "DexScreener Boosts v1",
            "GMGN.ai Sol Trench Radar",
        ],
        "auto_tp_pct": 8.0,
        "auto_sl_pct": 5.0,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 3.0,
        "time_stop_minutes": 10,
        "max_open_positions": 8,
        "tick_interval_ms": 1200,
    },
}

_SNIPER_CONFIG: dict = {
    "strategy_mode": "DEFAULT",  # SAFE | DEFAULT | AGGRESSIVE
    "strategy_label": STRATEGY_PRESETS["DEFAULT"]["strategy_label"],
    "strategy_desc": STRATEGY_PRESETS["DEFAULT"]["strategy_desc"],
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
    "only_new_creations": False,
    "max_token_age_minutes": 2880,
    "max_market_cap_usd": 50000000.0,
    "min_5m_buys": 5,
    "discovery_sources": ["DexScreener Final Stretch", "GMGN.ai Momentum"],
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
    "max_open_positions": 5,
    "tick_interval_ms": 3000,
}


def get_sniper_config() -> dict:
    cfg = dict(_SNIPER_CONFIG)
    cfg["presets"] = STRATEGY_PRESETS
    cfg["legacy_blacklist"] = sorted(list(market.LEGACY_ESTABLISHED_TOKENS))
    return cfg


def update_sniper_config(updates: dict) -> dict:
    req_strategy = updates.get("strategy_mode")
    apply_preset = bool(updates.get("apply_preset", False))
    if req_strategy:
        norm_strat = str(req_strategy).strip().upper()
        if norm_strat in STRATEGY_PRESETS:
            preset = STRATEGY_PRESETS[norm_strat]
            # If user clicked a mode preset button (or only sent strategy_mode), apply preset parameters
            if apply_preset or len([k for k, v in updates.items() if v is not None and k not in ("strategy_mode", "apply_preset")]) == 0:
                for pk, pv in preset.items():
                    _SNIPER_CONFIG[pk] = pv
            else:
                _SNIPER_CONFIG["strategy_mode"] = norm_strat
                _SNIPER_CONFIG["strategy_label"] = preset["strategy_label"]
                _SNIPER_CONFIG["strategy_desc"] = preset["strategy_desc"]
                _SNIPER_CONFIG["tick_interval_ms"] = preset["tick_interval_ms"]
                _SNIPER_CONFIG["max_open_positions"] = preset["max_open_positions"]
                _SNIPER_CONFIG["only_new_creations"] = preset["only_new_creations"]
                _SNIPER_CONFIG["discovery_sources"] = preset["discovery_sources"]

            _append_log(
                "SYSTEM",
                "SOL",
                norm_strat,
                f"Mode Strategi Bot diubah ke {preset['strategy_label']} — {preset['strategy_desc']}",
                f"TP +{_SNIPER_CONFIG['auto_tp_pct']}% / SL -{_SNIPER_CONFIG['auto_sl_pct']}% • Max Age {_SNIPER_CONFIG['max_token_age_minutes']}m",
                "success" if norm_strat != "AGGRESSIVE" else "warn",
            )

    # Support frontend alias keys (max_slippage_pct -> slippage_pct, snipe_amount_idr -> buy_amount_idr)
    if updates.get("max_slippage_pct") is not None and updates.get("slippage_pct") is None:
        updates["slippage_pct"] = updates["max_slippage_pct"]
    if updates.get("snipe_amount_idr") is not None and updates.get("buy_amount_idr") is None:
        updates["buy_amount_idr"] = updates["snipe_amount_idr"]

    for k, v in updates.items():
        if k in _SNIPER_CONFIG and v is not None and k not in ("strategy_mode",):
            _SNIPER_CONFIG[k] = v
    return get_sniper_config()


def get_bot_status(db: Session) -> BotState:
    state = db.execute(select(BotState).where(BotState.id == 1)).scalar_one_or_none()
    if not state:
        state = BotState(id=1, status="idle", mode="PAPER", total_trades=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def start_bot(db: Session, mode: str, strategy_mode: str | None = None) -> BotState:
    from app.services import live_engine

    norm_mode = (mode or "PAPER").strip().upper()
    if norm_mode not in ("PAPER", "LIVE"):
        norm_mode = "PAPER"

    if strategy_mode and strategy_mode.strip().upper() in STRATEGY_PRESETS:
        update_sniper_config({"strategy_mode": strategy_mode.strip().upper(), "apply_preset": True})

    strat_mode = _SNIPER_CONFIG.get("strategy_mode", "DEFAULT")
    strat_label = _SNIPER_CONFIG.get("strategy_label", "DEFAULT")

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
            "detail": f"Mode LIVE [{strat_mode}] Aktif ({w_name}: ${live_usd:,.2f} / Rp {live_idr:,.0f}) • Relay {_SNIPER_CONFIG['relay_mode']}...",
        })
        _append_log(
            "SYSTEM",
            "SOL",
            "ENGINE",
            f"🟢 Sniper Bot diaktifkan dalam Mode LIVE On-Chain • Strategi: {strat_label} (Hot Wallet: {w_name})",
            f"Saldo Live: Rp {live_idr:,.0f}",
            "success",
        )
    else:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 0,
            "target_token": "SOL / BASE Pools",
            "detail": f"Memindai pasangan meme coin di DexScreener Live (Mode PAPER • Strategi {strat_mode})...",
        })
        _append_log(
            "SYSTEM",
            "SOL",
            "ENGINE",
            f"Sniper Bot diaktifkan dalam mode {norm_mode} • Strategi: {strat_label}",
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
    strat_mode = (_SNIPER_CONFIG.get("strategy_mode") or "DEFAULT").upper()

    if state.status != "running":
        return {
            "status": state.status,
            "mode": state.mode,
            "strategy_mode": strat_mode,
            "sniper_config": get_sniper_config(),
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
            "trade_executed": False,
        }

    pulse = market.get_live_pulse_feed()
    new_creations = pulse.get("new_creations") or []
    final_stretch = pulse.get("final_stretch") or []
    migrated = pulse.get("migrated") or []

    max_age_mins = float(_SNIPER_CONFIG.get("max_token_age_minutes", 180 if strat_mode == "AGGRESSIVE" else 2880))
    max_mcap_usd = float(_SNIPER_CONFIG.get("max_market_cap_usd", 500000.0 if strat_mode == "AGGRESSIVE" else 50000000.0))

    # Candidate ordering depends on Strategy Mode:
    # - AGGRESSIVE: Strictly newly launched meme coins (DexScreener Token Profiles v1 + GMGN Trench), NEVER legacy tokens like BONK!
    # - SAFE: Prioritizes graduated/migrated pools with established liquidity
    # - DEFAULT: Balanced across all pools
    if strat_mode == "AGGRESSIVE":
        raw_aggressive = [
            c for c in (new_creations + final_stretch)
            if not market.is_legacy_token(c.get("base_symbol") or c.get("symbol", ""))
            and float(c.get("market_cap", 0)) <= max(max_mcap_usd, 800000.0)
        ]
        if not raw_aggressive:
            raw_aggressive = [
                c for c in market.fetch_dexscreener_latest_new_creations(usd_idr, limit=20)
                if not market.is_legacy_token(c.get("base_symbol") or c.get("symbol", ""))
            ]
        candidates = raw_aggressive
    elif strat_mode == "SAFE":
        candidates = migrated + final_stretch + new_creations
    else:
        candidates = final_stretch + migrated + new_creations

    holdings = list(db.execute(select(PortfolioHolding)).scalars().all())

    if not candidates:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 1,
            "target_token": "DexScreener / GMGN New Pairs",
            "detail": f"[{strat_mode}] Memindai DexScreener Token Profiles v1 & GMGN.ai untuk mencari koin meme yang baru rilis...",
        })
        return {
            "status": state.status,
            "mode": state.mode,
            "strategy_mode": strat_mode,
            "sniper_config": get_sniper_config(),
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
            "trade_executed": False,
        }

    min_score = int(_SNIPER_CONFIG.get("min_safety_score", 70))
    min_liq = float(_SNIPER_CONFIG.get("min_liquidity_usd", 5000.0))
    held_symbols = {h.symbol.upper() for h in holdings}

    if strat_mode == "AGGRESSIVE":
        # Strictly pick from brand-new non-legacy meme coins (prefer age <= max_age_mins & mcap <= max_mcap_usd)
        strict_fresh = [
            c for c in candidates
            if c["symbol"].upper() not in held_symbols
            and not market.is_legacy_token(c.get("base_symbol") or c["symbol"])
            and float(c.get("age_minutes", c.get("age_hours", 1.0) * 60.0)) <= max_age_mins
            and float(c.get("market_cap", 0)) <= max_mcap_usd
        ]
        if not strict_fresh:
            strict_fresh = [
                c for c in candidates
                if c["symbol"].upper() not in held_symbols
                and not market.is_legacy_token(c.get("base_symbol") or c["symbol"])
            ]
        pool_to_pick = strict_fresh if strict_fresh else [
            c for c in candidates if not market.is_legacy_token(c.get("base_symbol") or c["symbol"])
        ][: min(6, len(candidates))]
    elif strat_mode == "SAFE":
        safe_pool = [
            c for c in (migrated + final_stretch)
            if c.get("safety_score", 0) >= min_score
            and c.get("liquidity", 0) >= min_liq
            and c["symbol"].upper() not in held_symbols
        ]
        pool_to_pick = safe_pool if safe_pool else candidates[: min(5, len(candidates))]
    else:
        eligible = [
            c for c in candidates
            if c.get("safety_score", 0) >= min_score
            and c.get("liquidity", 0) >= min_liq
            and c["symbol"].upper() not in held_symbols
        ]
        pool_to_pick = eligible if eligible else candidates[: min(8, len(candidates))]

    pick = random.choice(pool_to_pick)

    sym = pick["symbol"]
    contract_addr = pick.get("contract") or ""
    ca_short = f"{contract_addr[:6]}...{contract_addr[-4:]}" if len(contract_addr) >= 12 else "On-Chain"
    chain = pick.get("chain", "Solana").upper()[:4]
    price_usd = pick["price"]
    price_idr = price_usd * usd_idr
    liq_usd = pick["liquidity"]
    mcap_usd = pick.get("market_cap", 0.0)
    vol_5m = pick["volume_5m"]
    score = pick["safety_score"]
    age_label = pick.get("age", "BARU")
    gmgn_degens = pick.get("gmgn_smart_degens", 3)

    # In AGGRESSIVE mode, fast-track execution: jump straight from stage 1 (Fast Scan) to stage 4 (Instant Snipe & Quick Scalp)!
    cur_idx = _CURRENT_STAGE.get("stage_index", 0)
    if force_trade:
        next_idx = 4
    elif strat_mode == "AGGRESSIVE":
        next_idx = 4 if cur_idx in (1, 2, 3) else 1
    else:
        next_idx = (cur_idx % 4) + 1

    if next_idx == 1:
        tag = f"🔥 DEXSCREENER + GMGN NEW-MEME RADAR (Umur {age_label})" if strat_mode == "AGGRESSIVE" else f"[{strat_mode}] SCANNING"
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 1,
            "target_token": sym,
            "detail": (
                f"[{active_mode} • {tag}] Koin baru {sym} ({pick.get('launchpad', 'Pump.fun')} • CA {ca_short}) "
                f"• Umur {age_label} • MCap ${mcap_usd:,.0f} • Liq ${liq_usd:,.0f} • GMGN Smart {gmgn_degens}W"
            ),
        })
        _append_log(
            "SCAN",
            chain,
            sym,
            (
                f"[{strat_mode}] {'KOIN BARU DEXSCREENER/GMGN' if strat_mode == 'AGGRESSIVE' else 'Pool Aktif'} "
                f"({age_label} • {pick.get('launchpad')} • CA {ca_short}) | MCap ${mcap_usd:,.0f} | Vol 5m ${vol_5m:,.0f} | GMGN {gmgn_degens}W"
            ),
            f"≈ Rp {price_idr:,.2f}",
            "info",
        )
    elif next_idx == 2:
        _CURRENT_STAGE.update({
            "stage": "RUG_SHIELD_AUDIT",
            "stage_index": 2,
            "target_token": sym,
            "detail": f"[{active_mode} • {strat_mode}] Memeriksa kontrak {sym} ({ca_short}): Mint/Freeze Revoked, LP Lock & Konsentrasi Top 10 Holder ({pick['top10_pct']}%)",
        })
        lvl = "success" if score >= 75 else "warn"
        _append_log(
            "AUDIT",
            chain,
            sym,
            f"[{strat_mode}] Kontrak Bersih (Score: {score}/100) | Top10 Non-AMM: {pick['top10_pct']}% | Liq/MCap sehat",
            "LOLOS FILTER" if score >= min_score else "WASPADA DUMP",
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
            "detail": f"[{active_mode} • {strat_mode}] Menganalisis orderflow 5m {sym}: {buys} Buys vs {sells} Sells (Δ {chg:+.2f}%) • Siap Auto-Snipe di tahap 4",
        })
        _append_log(
            "SIGNAL",
            chain,
            sym,
            f"[{strat_mode}] Momentum 5m {chg:+.2f}% ({buys}B/{sells}S) | Bonding Curve {pick['bonding_curve_pct']}% | GMGN Smart {gmgn_degens}W",
            f"MCap ${mcap_usd:,.0f}",
            "success" if chg >= 0 else "info",
        )
    else:
        # Check 05:00 WIB daily profit settlement schedule
        treasury.check_and_run_0500_wib_schedule(db)

        paper_wallet, _ = portfolio.get_or_create_paper_wallet(db)
        if active_mode == "LIVE":
            live_w, avail_cash_usd, _ = live_engine.get_live_trading_wallet(db, "Solana")
            spl_tokens = live_engine.query_solana_spl_tokens(live_w.address) if (live_w and live_w.chain == "Solana" and live_w.address) else []
            spl_usd = sum(t.get("usd_val", 0.0) for t in spl_tokens)
            total_live_cash_usd = avail_cash_usd + spl_usd
            avail_cash_idr = total_live_cash_usd * usd_idr

            # Calculate spendable SOL (reserve 0.0025 SOL for Solana ATA rent + gas fee)
            sol_bal = float(live_w.balance or 0.0) if live_w else 0.0
            sol_px = live_engine.get_sol_price_usd()
            spendable_sol = max(0.0, sol_bal - 0.0025)
            spendable_sol_idr = spendable_sol * sol_px * usd_idr
        else:
            treasury.ensure_gas_reserve(db, paper_wallet, usd_idr, needed_gas_usd=0.015)
            avail_cash_usd = float(paper_wallet.balance)
            avail_cash_idr = avail_cash_usd * usd_idr
            spendable_sol_idr = avail_cash_idr

        tp_target = float(_SNIPER_CONFIG.get("auto_tp_pct", 12.0))
        sl_target = -abs(float(_SNIPER_CONFIG.get("auto_sl_pct", 8.0)))
        tp_sell_pct = float(_SNIPER_CONFIG.get("auto_tp_sell_pct", 100.0))
        max_positions = int(_SNIPER_CONFIG.get("max_open_positions", 5))

        # 0. In AGGRESSIVE mode, immediately liquidate any legacy/old coin (e.g., BONK, PEPE, WIF) left over in holdings
        # so capital is freed up to snipe genuine newly created meme coins!
        if strat_mode == "AGGRESSIVE" and auto_trade:
            for h in list(holdings):
                if market.is_legacy_token(h.symbol):
                    try:
                        cleanup_res = portfolio.sell_holding(db, h.symbol, 100.0, mode=active_mode)
                        state.total_trades = (state.total_trades or 0) + 1
                        db.commit()
                        _append_log(
                            "SNIPE",
                            "SOL",
                            h.symbol,
                            f"[{active_mode} • AGGRESSIVE CLEANUP] Menjual 100% koin lama {h.symbol} karena bukan koin baru (merotasi modal ke New Creations DexScreener/GMGN)",
                            f"Kas ({active_mode}): Rp {cleanup_res['cash_remaining_idr']:,.0f}",
                            "warn",
                        )
                    except Exception:
                        pass
            holdings = list(db.execute(select(PortfolioHolding)).scalars().all())
            if active_mode != "LIVE":
                db.refresh(paper_wallet)
                avail_cash_usd = float(paper_wallet.balance)
                avail_cash_idr = avail_cash_usd * usd_idr

        # 1. Refresh live prices on existing holdings & check Auto TP / SL (or Fast Scalp Flip in AGGRESSIVE mode)
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

            # In AGGRESSIVE mode, also trigger Quick Scalp Profit if net_pnl_pct >= 2.5% or rotate oldest position when slots are full
            fast_scalp_hit = (strat_mode == "AGGRESSIVE") and (net_pnl_pct >= 2.5 or len(holdings) >= max_positions)
            should_exit = auto_trade and (net_pnl_pct >= tp_target or net_pnl_pct <= sl_target or fast_scalp_hit)

            if should_exit:
                try:
                    sell_pct = tp_sell_pct if net_pnl_pct >= tp_target else 100.0
                    sell_res = portfolio.sell_holding(db, h.symbol, sell_pct, mode=active_mode)
                    state.total_trades = (state.total_trades or 0) + 1
                    db.commit()
                    if net_pnl_pct >= tp_target:
                        reason = f"AUTO TAKE-PROFIT [{strat_mode}]"
                    elif fast_scalp_hit and net_pnl_pct >= 0:
                        reason = "⚡ AGGRESSIVE FAST SCALP TAKE-PROFIT"
                    elif fast_scalp_hit:
                        reason = "⚡ AGGRESSIVE FAST ROTATION EXIT"
                    else:
                        reason = f"AUTO STOP-LOSS [{strat_mode}]"

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

        # 2. Auto-Snipe new token if we have sufficient spendable Cash and open positions < max_positions
        score_threshold = (min_score - 15) if strat_mode == "AGGRESSIVE" else (min_score - 5)
        min_cash_threshold = 2000.0 if active_mode == "LIVE" else 5000.0
        has_enough_cash = (spendable_sol_idr >= min_cash_threshold) if active_mode == "LIVE" else (avail_cash_idr >= min_cash_threshold)

        can_snipe = (
            not sold_any
            and auto_trade
            and has_enough_cash
            and len(holdings) < max_positions
            and score >= score_threshold
        )

        if can_snipe:
            cfg_buy_idr = float(_SNIPER_CONFIG.get("buy_amount_idr", 15000.0))
            if active_mode == "LIVE":
                # Adapt buy size to available spendable SOL cash, bounded by cfg_buy_idr
                snipe_idr = min(cfg_buy_idr, max(2000.0, spendable_sol_idr))
            else:
                snipe_idr = min(cfg_buy_idr, round(avail_cash_idr * 0.25, -2))
                if snipe_idr < 10000.0:
                    snipe_idr = min(15000.0, avail_cash_idr)
            try:
                snipe_res = memecoins.execute_snipe(
                    db,
                    {
                        "symbol": sym,
                        "contract": contract_addr,
                        "price": price_usd,
                        "amount_idr": snipe_idr,
                        "slippage_pct": float(_SNIPER_CONFIG.get("slippage_pct", 1.0)),
                        "priority_fee_sol": float(_SNIPER_CONFIG.get("priority_fee_sol", 0.005)),
                        "anti_mev": bool(_SNIPER_CONFIG.get("anti_mev", True)),
                        "force_unsafe": strat_mode == "AGGRESSIVE",
                        "block_legacy_tokens": strat_mode == "AGGRESSIVE",
                        "mode": active_mode,
                    },
                )
                state.total_trades = (state.total_trades or 0) + 1
                db.commit()
                snipe_tag = f"🔥 DEXSCREENER+GMGN NEW-MEME SNIPE ({age_label})" if strat_mode == "AGGRESSIVE" else f"AUTO-SNIPE [{strat_mode}]"
                _CURRENT_STAGE.update({
                    "stage": "AUTO_SNIPE_MONITOR",
                    "stage_index": 4,
                    "target_token": snipe_res["symbol"],
                    "detail": (
                        f"⚡ [{active_mode} • {snipe_tag}] FILLED: Beli {snipe_res['symbol']} ({pick.get('launchpad', 'Pump.fun')} • CA {ca_short}) "
                        f"Rp {snipe_idr:,.0f} @ ${snipe_res['entry_price']:.6f} (Slip {snipe_res['slippage_pct']:.2f}% • Gas Rp {snipe_res['gas_fee_idr']:,.0f})"
                    ),
                })
                _append_log(
                    "SNIPE",
                    chain,
                    snipe_res["symbol"],
                    (
                        f"[{active_mode} • {snipe_tag}] TERBELI Rp {snipe_idr:,.0f} @ ${snipe_res['entry_price']:.6f} | "
                        f"TX: {snipe_res.get('tx_hash', '')[:12]}... (Anti-MEV Jito)"
                    ),
                    f"Rp {snipe_idr:,.0f}",
                    "success",
                )
                trade_executed = True
                trade_action = snipe_res
            except Exception as exc:
                _CURRENT_STAGE.update({
                    "stage": "AUTO_SNIPE_MONITOR",
                    "stage_index": 4,
                    "target_token": sym,
                    "detail": f"⚠️ [{active_mode}] Gagal/Lewati Auto-Snipe {sym}: {exc}",
                })
                _append_log(
                    "SYSTEM",
                    chain,
                    sym,
                    f"[{active_mode}] Gagal/Lewati Auto-Snipe {sym}: {exc}",
                    f"Rp {snipe_idr:,.0f}",
                    "warn",
                )
        elif not sold_any:
            # Diagnose exact reason why auto-snipe did not execute on this tick
            skip_reason = ""
            if not auto_trade:
                skip_reason = "Saklar 'Otomatis Eksekusi Swap' nonaktif (mode monitoring saja)"
            elif not has_enough_cash:
                cash_label = f"SOL Kas Rp {spendable_sol_idr:,.0f}" if active_mode == "LIVE" else f"Kas Rp {avail_cash_idr:,.0f}"
                skip_reason = f"{cash_label} < batas minimal beli Rp {min_cash_threshold:,.0f}"
            elif len(holdings) >= max_positions:
                skip_reason = f"Slot open positions penuh ({len(holdings)}/{max_positions})"
            elif score < score_threshold:
                skip_reason = f"Skor Keamanan {score:.0f} di bawah batas minimal {score_threshold:.0f} [{strat_mode}] (Anti-Rug Guard aktif)"

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
                        f"[{active_mode} • {strat_mode}] Memantau {len(holdings)} posisi ({h.symbol} Net PnL: {net_pnl_pct:+.2f}% | Gross: {gross_pnl_pct:+.2f}% "
                        f"setelah est. Slippage+DEX+Gas Rp {net_m['est_exit_cost_idr']:,.0f}) • Target Net TP +{tp_target}%"
                        + (f" • Skip buy {sym}: {skip_reason}" if skip_reason else "")
                    ),
                })
                _append_log(
                    "MONITOR",
                    "SOL",
                    h.symbol,
                    f"[{active_mode} • {strat_mode}] Live ${h.current_price:.6f} | Net PnL: {net_pnl_pct:+.2f}% (setelah Slippage {net_m['exit_slippage_pct']:.2f}%, DEX & Gas)"
                    + (f" | {skip_reason}" if skip_reason else ""),
                    f"Net ≈ Rp {net_m['net_value_usd'] * usd_idr:,.0f}",
                    "success" if net_pnl_pct >= 0 else "warn",
                )
            else:
                _CURRENT_STAGE.update({
                    "stage": "MEV_STANDBY",
                    "stage_index": 4,
                    "target_token": sym,
                    "detail": f"[{active_mode} • {strat_mode}] Kas Rp {avail_cash_idr:,.0f}. Menunggu koin lolos kriteria: {skip_reason}.",
                })
                if skip_reason and score < score_threshold:
                    _append_log(
                        "AUDIT",
                        chain,
                        sym,
                        f"[{active_mode} • ANTI-RUG GUARD] Lewati {sym} ({pick.get('launchpad', 'Pump.fun')}) - {skip_reason}",
                        f"Skor {score:.0f}",
                        "warn",
                    )

    return {
        "status": state.status,
        "mode": state.mode,
        "strategy_mode": strat_mode,
        "total_trades": state.total_trades or 0,
        "sniper_config": get_sniper_config(),
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

