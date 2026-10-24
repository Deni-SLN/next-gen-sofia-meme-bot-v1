import json
import os
import random
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.db.models import BotState, PortfolioHolding
from app.services import market, portfolio, memecoins

_CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "sniper_config.json"
_TICK_LOCK = threading.Lock()
_LAST_TICK_TS: float = 0.0
_LAST_TICK_RESULT: dict | None = None

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


_RECENT_SL_COOLDOWN: dict[str, float] = {}
_PEAK_NET_PNL_PCT: dict[str, float] = {}
_HOLDING_ENTRY_TS: dict[str, float] = {}
SL_COOLDOWN_SECONDS: float = 1800.0  # 30 minutes cooldown after a stop-loss


def clear_bot_logs() -> None:
    _BOT_ACTIVITY_LOGS.clear()
    _RECENT_SL_COOLDOWN.clear()
    _PEAK_NET_PNL_PCT.clear()
    _HOLDING_ENTRY_TS.clear()
    cap_idr = float(_SNIPER_CONFIG.get("paper_initial_capital_idr", 150000.0))
    _CURRENT_STAGE.update({
        "stage": "IDLE",
        "stage_index": 0,
        "target_token": None,
        "detail": f"Modal Paper telah di-reset ke Rp {cap_idr:,.0f}. Siap memindai market.",
    })
    _append_log("SYSTEM", "SOL", "RESET", f"Semua portofolio & posisi Paper dihapus. Modal kembali ke Rp {cap_idr:,.0f}.", f"Rp {cap_idr:,.0f}", "info")


def _trig_tag() -> str:
    strat = str(_SNIPER_CONFIG.get("strategy_mode", "DEFAULT")).upper()
    return f"[{strat}]"


STRATEGY_PRESETS: dict[str, dict] = {
    "SAFE": {
        "strategy_mode": "SAFE",
        "strategy_label": "🛡️ SAFE (Konservatif • Token Lulus & Likuiditas Tinggi)",
        "strategy_desc": "Hanya membeli token yang sudah Migrated (Raydium/PumpSwap) dengan likuiditas > $20K & Safety Score ≥ 82.",
        "relay_mode": "JITO_0SLOT",
        "slippage_pct": 0.8,
        "priority_fee_sol": 0.0005,
        "jito_bribe_sol": 0.0005,
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
        "auto_tp_pct": 20.0,
        "auto_sl_pct": 8.0,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 5.0,
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
        "priority_fee_sol": 0.0008,
        "jito_bribe_sol": 0.0008,
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
        "auto_tp_pct": 30.0,
        "auto_sl_pct": 10.0,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 6.0,
        "time_stop_minutes": 30,
        "max_open_positions": 5,
        "tick_interval_ms": 3000,
    },
    "AGGRESSIVE": {
        "strategy_mode": "AGGRESSIVE",
        "strategy_label": "🔥 AGRESIF (DexScreener + GMGN.ai New Meme Sniper • Koin Baru & Cepat)",
        "strategy_desc": "Khusus menyergap meme coin BARU MUNCUL (New Creations < 3 Jam, MCap < $500K) via DexScreener Token Profiles v1 & GMGN.ai Trench Radar. Memblokir 100% koin lama seperti BONK/PEPE/WIF.",
        "relay_mode": "JITO_0SLOT",
        "slippage_pct": 2.0,
        "priority_fee_sol": 0.0010,
        "jito_bribe_sol": 0.0010,
        "buy_amount_idr": 20000.0,
        "min_safety_score": 60,
        "min_liquidity_usd": 2000.0,
        "min_bonding_curve_pct": 15.0,
        "max_dev_holding_pct": 15.0,
        "only_new_creations": True,
        "max_token_age_minutes": 180,
        "max_market_cap_usd": 500000.0,
        "min_5m_buys": 4,
        "discovery_sources": [
            "DexScreener Token Profiles v1",
            "DexScreener Boosts v1",
            "GMGN.ai Sol Trench Radar",
        ],
        "auto_tp_pct": 8.0,
        "auto_sl_pct": 5.5,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 2.5,
        "time_stop_minutes": 20,
        "max_open_positions": 5,
        "tick_interval_ms": 1200,
    },
}

_SNIPER_CONFIG: dict = {
    "strategy_mode": "DEFAULT",  # SAFE | DEFAULT | AGGRESSIVE
    "strategy_label": STRATEGY_PRESETS["DEFAULT"]["strategy_label"],
    "strategy_desc": STRATEGY_PRESETS["DEFAULT"]["strategy_desc"],
    "relay_mode": "JITO_0SLOT",  # JITO_0SLOT | HELIUS_STAKED | BLOXROUTE | MAINNET_STD
    "slippage_pct": 1.2,
    "priority_fee_sol": 0.0008,
    "jito_bribe_sol": 0.0008,
    "anti_mev": True,
    "buy_amount_idr": 20000.0,
    "min_safety_score": 70,
    "min_liquidity_usd": 5000.0,
    "min_bonding_curve_pct": 20.0,
    "max_bonding_curve_pct": 98.0,
    "max_dev_holding_pct": 12.0,
    "max_top10_holding_pct": 35.0,
    "only_new_creations": False,
    "max_token_age_minutes": 2880,
    "max_market_cap_usd": 50000000.0,
    "min_5m_buys": 5,
    "discovery_sources": ["DexScreener Final Stretch", "GMGN.ai Momentum"],
    "require_mint_revoked": True,
    "require_freeze_revoked": True,
    "require_lp_burned": True,
    "auto_tp_pct": 30.0,
    "auto_tp_sell_pct": 100.0,
    "auto_sl_pct": 10.0,
    "trailing_stop_enabled": True,
    "trailing_stop_pct": 6.0,
    "time_stop_minutes": 30,
    "multi_wallet_rotation": True,
    "max_open_positions": 5,
    "tick_interval_ms": 3000,
}


def _load_persisted_sniper_config() -> None:
    """Load persisted sniper config from disk so strategy_mode never resets to DEFAULT across reloads or workers."""
    try:
        if _CONFIG_FILE_PATH.exists():
            data = json.loads(_CONFIG_FILE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if (k in _SNIPER_CONFIG or k in _USER_OWNED_KEYS) and v is not None:
                        _SNIPER_CONFIG[k] = v
                strat = str(_SNIPER_CONFIG.get("strategy_mode", "DEFAULT")).upper()
                if strat in STRATEGY_PRESETS:
                    _SNIPER_CONFIG["strategy_label"] = STRATEGY_PRESETS[strat]["strategy_label"]
                    _SNIPER_CONFIG["strategy_desc"] = STRATEGY_PRESETS[strat]["strategy_desc"]
                # Migrate legacy inverted AGGRESSIVE SL (8.0 / 12.0) to positive R:R (8.0 / 5.5)
                if strat == "AGGRESSIVE" and float(_SNIPER_CONFIG.get("auto_sl_pct", 5.5)) >= 10.0:
                    _SNIPER_CONFIG["auto_tp_pct"] = 8.0
                    _SNIPER_CONFIG["auto_sl_pct"] = 5.5
                    _SNIPER_CONFIG["trailing_stop_pct"] = 2.5
    except Exception:
        pass


def _save_persisted_sniper_config() -> None:
    """Persist sniper config to disk immediately on change."""
    try:
        _CONFIG_FILE_PATH.write_text(json.dumps(_SNIPER_CONFIG, indent=2), encoding="utf-8")
    except Exception:
        pass


_load_persisted_sniper_config()


_USER_OWNED_KEYS = (
    "buy_amount_idr",
    "snipe_amount_idr",
    "max_open_positions",
    "slippage_pct",
    "max_slippage_pct",
    "paper_initial_capital_idr",
    "buy_amount_usd",
)


def get_strategy_winrate_stats(db: Session | None = None, mode: str | None = None) -> dict[str, dict]:
    """
    Return genuine winrate, trade counts, wins, losses, and realized PnL for each strategy mode
    (SAFE, DEFAULT, AGGRESSIVE) computed strictly from real closed trades, including separate
    PAPER and LIVE breakdowns.
    """
    from app.db.models import Trade

    def _empty_bucket(s_mode: str) -> dict:
        return {
            "strategy_mode": s_mode,
            "winrate_pct": None,
            "trades_count": 0,
            "wins": 0,
            "losses": 0,
            "realized_pnl_idr": 0.0,
            "paper_winrate_pct": 0.0,
            "paper_trades_count": 0,
            "paper_wins": 0,
            "paper_losses": 0,
            "paper_realized_pnl_idr": 0.0,
            "live_winrate_pct": 0.0,
            "live_trades_count": 0,
            "live_wins": 0,
            "live_losses": 0,
            "live_realized_pnl_idr": 0.0,
        }

    stats: dict[str, dict] = {
        "SAFE": _empty_bucket("SAFE"),
        "DEFAULT": _empty_bucket("DEFAULT"),
        "AGGRESSIVE": _empty_bucket("AGGRESSIVE"),
    }

    if db is not None:
        try:
            fx = market.get_fx_rate()
            usd_idr = fx.get("usd_idr", 16300.0)
            q = select(Trade).where(
                Trade.status == "closed",
                or_(Trade.side == "sell", Trade.pnl != 0),
            )
            closed_sells = list(db.execute(q).scalars().all())
            for t in closed_sells:
                if getattr(t, "result", None) == "ORPHAN_CLEARED":
                    continue
                notes_u = (t.notes or "").upper()
                if "[SAFE]" in notes_u:
                    m_key = "SAFE"
                elif "[AGGRESSIVE]" in notes_u:
                    m_key = "AGGRESSIVE"
                else:
                    m_key = "DEFAULT"

                t_mode = str(t.mode or "PAPER").upper()
                pnl_val_usd = float(t.pnl or 0.0)
                pnl_idr = pnl_val_usd * usd_idr
                is_win = pnl_val_usd > 0

                if t_mode == "LIVE":
                    stats[m_key]["live_trades_count"] += 1
                    stats[m_key]["live_realized_pnl_idr"] += pnl_idr
                    if is_win:
                        stats[m_key]["live_wins"] += 1
                    else:
                        stats[m_key]["live_losses"] += 1
                else:
                    stats[m_key]["paper_trades_count"] += 1
                    stats[m_key]["paper_realized_pnl_idr"] += pnl_idr
                    if is_win:
                        stats[m_key]["paper_wins"] += 1
                    else:
                        stats[m_key]["paper_losses"] += 1

                if not mode or t_mode == mode.upper():
                    stats[m_key]["trades_count"] += 1
                    stats[m_key]["realized_pnl_idr"] += pnl_idr
                    if is_win:
                        stats[m_key]["wins"] += 1
                    else:
                        stats[m_key]["losses"] += 1

            for m_key, s in stats.items():
                s["realized_pnl_idr"] = round(s["realized_pnl_idr"], 0)
                s["paper_realized_pnl_idr"] = round(s["paper_realized_pnl_idr"], 0)
                s["live_realized_pnl_idr"] = round(s["live_realized_pnl_idr"], 0)
                tc = s["trades_count"]
                if tc > 0:
                    s["winrate_pct"] = round((s["wins"] / tc) * 100.0, 1)
                ptc = s["paper_trades_count"]
                if ptc > 0:
                    s["paper_winrate_pct"] = round((s["paper_wins"] / ptc) * 100.0, 1)
                ltc = s["live_trades_count"]
                if ltc > 0:
                    s["live_winrate_pct"] = round((s["live_wins"] / ltc) * 100.0, 1)
        except Exception:
            pass

    return stats


def get_sniper_config(db: Session | None = None, mode: str | None = None) -> dict:
    _load_persisted_sniper_config()
    cfg = dict(_SNIPER_CONFIG)
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16300.0)
    cfg["buy_amount_usd"] = round(float(cfg.get("buy_amount_idr", 20000.0)) / usd_idr, 2)
    cfg["presets"] = STRATEGY_PRESETS
    cfg["strategy_stats"] = get_strategy_winrate_stats(db, mode=mode)
    cfg["legacy_blacklist"] = sorted(list(market.LEGACY_ESTABLISHED_TOKENS))
    return cfg

def update_sniper_config(updates: dict, db: Session | None = None, allow_while_running: bool = False) -> dict:
    _load_persisted_sniper_config()
    req_strategy = updates.get("strategy_mode")
    apply_preset = bool(updates.get("apply_preset", False))
    current_strat = str(_SNIPER_CONFIG.get("strategy_mode", "DEFAULT")).strip().upper()

    if req_strategy:
        norm_strat = str(req_strategy).strip().upper()
        if norm_strat in STRATEGY_PRESETS:
            preset = STRATEGY_PRESETS[norm_strat]
            # Preserve user owned keys so strategy preset never clobbers operator trade size / positions / slippage
            preserved_user = {k: _SNIPER_CONFIG[k] for k in _USER_OWNED_KEYS if k in _SNIPER_CONFIG}
            if apply_preset or len([k for k, v in updates.items() if v is not None and k not in ("strategy_mode", "apply_preset")]) == 0:
                for pk, pv in preset.items():
                    _SNIPER_CONFIG[pk] = pv
                for k, v in preserved_user.items():
                    _SNIPER_CONFIG[k] = v
            else:
                _SNIPER_CONFIG["strategy_mode"] = norm_strat
                _SNIPER_CONFIG["strategy_label"] = preset["strategy_label"]
                _SNIPER_CONFIG["strategy_desc"] = preset["strategy_desc"]
                _SNIPER_CONFIG["tick_interval_ms"] = preset["tick_interval_ms"]
                _SNIPER_CONFIG["max_open_positions"] = preset["max_open_positions"]
                _SNIPER_CONFIG["only_new_creations"] = preset["only_new_creations"]
                _SNIPER_CONFIG["discovery_sources"] = preset["discovery_sources"]
                for k, v in preserved_user.items():
                    _SNIPER_CONFIG[k] = v

            if norm_strat != current_strat or apply_preset:
                _append_log(
                    "SYSTEM",
                    "SOL",
                    norm_strat,
                    f"Mode Strategi Bot dikunci ke {preset['strategy_label']} — {preset['strategy_desc']}",
                    f"TP +{_SNIPER_CONFIG['auto_tp_pct']}% / SL -{_SNIPER_CONFIG['auto_sl_pct']}% • Max Age {_SNIPER_CONFIG['max_token_age_minutes']}m",
                    "success" if norm_strat != "AGGRESSIVE" else "warn",
                )

    # Support frontend alias keys and USD buy amounts (keep buy_amount_usd and buy_amount_idr 100% synced)
    fx = market.get_fx_rate()
    usd_idr = fx.get("usd_idr", 16300.0)
    if updates.get("buy_amount_usd") is not None and float(updates["buy_amount_usd"]) > 0:
        b_usd = round(float(updates["buy_amount_usd"]), 4)
        b_idr = round(b_usd * usd_idr, 0)
        updates["buy_amount_usd"] = b_usd
        updates["buy_amount_idr"] = b_idr
        updates["snipe_amount_idr"] = b_idr
        _SNIPER_CONFIG["buy_amount_usd"] = b_usd
    elif (updates.get("buy_amount_idr") is not None or updates.get("snipe_amount_idr") is not None):
        raw_idr = float(updates.get("buy_amount_idr") or updates.get("snipe_amount_idr") or 0.0)
        if raw_idr > 0:
            b_usd = round(raw_idr / usd_idr, 4)
            updates["buy_amount_idr"] = raw_idr
            updates["snipe_amount_idr"] = raw_idr
            updates["buy_amount_usd"] = b_usd
            _SNIPER_CONFIG["buy_amount_usd"] = b_usd

    if updates.get("max_slippage_pct") is not None and updates.get("slippage_pct") is None:
        updates["slippage_pct"] = updates["max_slippage_pct"]

    for k, v in updates.items():
        if (k in _SNIPER_CONFIG or k in _USER_OWNED_KEYS) and v is not None and k not in ("strategy_mode",):
            _SNIPER_CONFIG[k] = v
    _save_persisted_sniper_config()

    # If db is provided and PAPER holdings exceed max_open_positions or buy_amount_usd, trim immediately
    if db is not None:
        try:
            max_pos = max(1, int(_SNIPER_CONFIG.get("max_open_positions", 5)))
            paper_holdings = list(
                db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "PAPER")).scalars().all()
            )
            if len(paper_holdings) > max_pos:
                for excess_h in paper_holdings[max_pos:]:
                    try:
                        portfolio.sell_holding(db, excess_h.symbol, 100.0, mode="PAPER")
                    except Exception:
                        pass
        except Exception:
            pass

    return get_sniper_config(db)


def get_bot_status(db: Session) -> BotState:
    state = db.execute(select(BotState).where(BotState.id == 1)).scalar_one_or_none()
    if not state:
        state = BotState(id=1, status="idle", mode="PAPER", total_trades=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def start_bot(
    db: Session,
    mode: str,
    strategy_mode: str | None = None,
    buy_amount_usd: float | None = None,
    buy_amount_idr: float | None = None,
    max_open_positions: int | None = None,
    slippage_pct: float | None = None,
) -> BotState:
    from app.services import live_engine

    norm_mode = (mode or "PAPER").strip().upper()
    if norm_mode not in ("PAPER", "LIVE"):
        norm_mode = "PAPER"

    _load_persisted_sniper_config()
    if strategy_mode and strategy_mode.strip().upper() in STRATEGY_PRESETS:
        req_strat_norm = strategy_mode.strip().upper()
        cur_strat_norm = str(_SNIPER_CONFIG.get("strategy_mode", "DEFAULT")).strip().upper()
        update_sniper_config(
            {"strategy_mode": req_strat_norm, "apply_preset": req_strat_norm != cur_strat_norm},
            db=db,
            allow_while_running=True,
        )

    # Apply operator pre-start parameters (dollar per trade, max positions, slippage)
    runtime_updates: dict = {}
    if buy_amount_usd is not None and float(buy_amount_usd) > 0:
        runtime_updates["buy_amount_usd"] = float(buy_amount_usd)
    elif buy_amount_idr is not None and float(buy_amount_idr) > 0:
        runtime_updates["buy_amount_idr"] = float(buy_amount_idr)
    if max_open_positions is not None and int(max_open_positions) > 0:
        runtime_updates["max_open_positions"] = int(max_open_positions)
    if slippage_pct is not None and float(slippage_pct) > 0:
        runtime_updates["slippage_pct"] = float(slippage_pct)

    if runtime_updates:
        update_sniper_config(runtime_updates, db=db, allow_while_running=True)
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
    global _LAST_TICK_TS, _LAST_TICK_RESULT
    from app.services import treasury, live_engine

    _load_persisted_sniper_config()
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

    now_ts = time.monotonic()
    if not force_trade and _LAST_TICK_RESULT is not None and (now_ts - _LAST_TICK_TS) < 1.2:
        return {
            **_LAST_TICK_RESULT,
            "status": state.status,
            "mode": state.mode,
            "strategy_mode": strat_mode,
            "sniper_config": get_sniper_config(),
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
        }

    if not _TICK_LOCK.acquire(blocking=force_trade):
        return {
            "status": state.status,
            "mode": state.mode,
            "strategy_mode": strat_mode,
            "total_trades": state.total_trades or 0,
            "sniper_config": get_sniper_config(),
            "current_stage": _CURRENT_STAGE,
            "logs": _BOT_ACTIVITY_LOGS[:25],
            "usd_idr": usd_idr,
            "trade_executed": False,
        }

    try:
        return _run_bot_scan_tick_locked(db, state, usd_idr, active_mode, strat_mode, auto_trade, force_trade)
    finally:
        _LAST_TICK_TS = time.monotonic()
        _TICK_LOCK.release()


def _run_bot_scan_tick_locked(
    db: Session,
    state: BotState,
    usd_idr: float,
    active_mode: str,
    strat_mode: str,
    auto_trade: bool = True,
    force_trade: bool = False,
) -> dict:
    global _LAST_TICK_RESULT
    from app.services import treasury, live_engine

    trade_executed = False
    trade_action = None

    pulse = market.get_live_pulse_feed()
    new_creations = pulse.get("new_creations") or []
    final_stretch = pulse.get("final_stretch") or []
    migrated = pulse.get("migrated") or []

    if active_mode == "LIVE":
        def _valid_solana_live(c: dict) -> bool:
            ca = str(c.get("contract") or "").strip()
            ch = str(c.get("chain") or "Solana").strip().lower()
            return ch == "solana" and len(ca) >= 32 and not ca.startswith("0x")

        new_creations = [c for c in new_creations if _valid_solana_live(c)]
        final_stretch = [c for c in final_stretch if _valid_solana_live(c)]
        migrated = [c for c in migrated if _valid_solana_live(c)]

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
            and (active_mode != "LIVE" or _valid_solana_live(c))
        ]
        if not raw_aggressive:
            raw_aggressive = [
                c for c in market.fetch_dexscreener_latest_new_creations(usd_idr, limit=20)
                if not market.is_legacy_token(c.get("base_symbol") or c.get("symbol", ""))
                and (active_mode != "LIVE" or _valid_solana_live(c))
            ]
        candidates = raw_aggressive
    elif strat_mode == "SAFE":
        candidates = migrated + final_stretch + new_creations
    else:
        candidates = final_stretch + migrated + new_creations

    if active_mode == "LIVE":
        portfolio.sync_onchain_holdings_to_portfolio(db)
    holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())

    if not candidates:
        _CURRENT_STAGE.update({
            "stage": "SCANNING_DEX",
            "stage_index": 1,
            "target_token": "DexScreener / GMGN New Pairs",
            "detail": f"[{strat_mode}] Memindai DexScreener Token Profiles v1 & GMGN.ai untuk mencari koin meme yang sesuai kriteria...",
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
    score_threshold = (min_score - 15) if strat_mode == "AGGRESSIVE" else (min_score - 5)
    held_symbols = {h.symbol.upper() for h in holdings}
    held_bases = {h.symbol.upper().split("/")[0] for h in holdings}
    now_ts = time.time()

    def _not_held(c: dict) -> bool:
        sym_u = str(c.get("symbol") or "").upper()
        base_u = str(c.get("base_symbol") or sym_u.split("/")[0]).upper()
        ca_u = str(c.get("contract") or "").upper()
        if sym_u in held_symbols or base_u in held_bases:
            return False
        # Stop-Loss Cooldown Guard: prevent re-buying a token that recently triggered Stop-Loss
        for k in (sym_u, base_u, ca_u):
            if k and k in _RECENT_SL_COOLDOWN and (now_ts - _RECENT_SL_COOLDOWN[k]) < SL_COOLDOWN_SECONDS:
                return False
        return True

    def _has_bullish_orderflow(c: dict) -> bool:
        """Quantitative orderflow & momentum filter: require buyers >= sellers and non-dumping 5m/1m action."""
        buys = int(c.get("buys_5m", 0))
        sells = int(c.get("sells_5m", 0))
        chg_5m = float(c.get("price_change_5m", 0.0))
        chg_1m = float(c.get("price_change_1m", chg_5m / 5.0))
        r_bs = buys / max(1, sells)
        if sells > 0 and r_bs < 1.10:
            return False
        if chg_5m < -0.8 or chg_1m < -0.5:
            return False
        return True

    def _alpha_score(c: dict) -> float:
        """Composite institutional sniper score combining orderflow ratio R_bs, 5m momentum, liquidity velocity, and safety."""
        buys = int(c.get("buys_5m", 1))
        sells = int(c.get("sells_5m", 0))
        r_bs = min(6.0, buys / max(1, sells))
        chg_5m = min(35.0, max(-25.0, float(c.get("price_change_5m", 0.0))))
        vol_5m_val = float(c.get("volume_5m", 0.0))
        liq_val = max(1000.0, float(c.get("liquidity", 1000.0)))
        vol_vel = min(3.0, vol_5m_val / liq_val)
        s_score = float(c.get("safety_score", 65.0))
        degens = float(c.get("gmgn_smart_degens", 2))
        return (s_score * 0.7) + (r_bs * 12.0) + (chg_5m * 1.1) + (vol_vel * 10.0) + (degens * 1.5)

    if strat_mode == "AGGRESSIVE":
        # Strictly pick from brand-new non-legacy meme coins (prefer age <= max_age_mins, mcap <= max_mcap_usd, score >= score_threshold)
        strict_fresh = [
            c for c in candidates
            if _not_held(c)
            and not market.is_legacy_token(c.get("symbol") or c.get("base_symbol", ""))
            and float(c.get("age_minutes", c.get("age_hours", 1.0) * 60.0)) <= max_age_mins
            and float(c.get("market_cap", 0)) <= max_mcap_usd
            and float(c.get("safety_score", 0)) >= score_threshold
            and float(c.get("liquidity", 0)) >= min(min_liq, 1500.0)
        ]
        if not strict_fresh:
            strict_fresh = [
                c for c in candidates
                if _not_held(c)
                and not market.is_legacy_token(c.get("symbol") or c.get("base_symbol", ""))
                and float(c.get("safety_score", 0)) >= score_threshold
            ]
        pool_to_pick = strict_fresh if strict_fresh else [
            c for c in candidates if _not_held(c) and not market.is_legacy_token(c.get("symbol") or c.get("base_symbol", ""))
        ][: min(6, len(candidates))]
    elif strat_mode == "SAFE":
        graduated_candidates = migrated + final_stretch
        safe_pool = [
            c for c in graduated_candidates
            if _not_held(c)
            and float(c.get("safety_score", 0)) >= min_score
            and float(c.get("liquidity", 0)) >= min_liq
        ]
        if not safe_pool:
            safe_pool = sorted(
                [
                    c for c in graduated_candidates
                    if _not_held(c)
                    and float(c.get("safety_score", 0)) >= score_threshold
                    and float(c.get("liquidity", 0)) >= min(min_liq * 0.5, 10000.0)
                ],
                key=lambda x: (float(x.get("safety_score", 0)), float(x.get("liquidity", 0))),
                reverse=True,
            )[:5]
        pool_to_pick = safe_pool if safe_pool else sorted(
            [c for c in candidates if _not_held(c)],
            key=lambda x: (float(x.get("safety_score", 0)), float(x.get("liquidity", 0))),
            reverse=True,
        )[: min(5, len(candidates))]
    else:
        eligible = [
            c for c in candidates
            if _not_held(c)
            and float(c.get("safety_score", 0)) >= min_score
            and float(c.get("liquidity", 0)) >= min_liq
        ]
        if not eligible:
            eligible = sorted(
                [
                    c for c in candidates
                    if _not_held(c)
                    and float(c.get("safety_score", 0)) >= score_threshold
                    and float(c.get("liquidity", 0)) >= min(min_liq * 0.6, 3000.0)
                ],
                key=lambda x: (float(x.get("safety_score", 0)), float(x.get("volume_5m", 0))),
                reverse=True,
            )[:6]
        pool_to_pick = eligible if eligible else [c for c in candidates if _not_held(c)][: min(8, len(candidates))]

    unheld_candidates = [c for c in candidates if _not_held(c)]
    has_unheld_candidate = len(unheld_candidates) > 0
    if not pool_to_pick:
        pool_to_pick = unheld_candidates[: min(5, len(unheld_candidates))] if unheld_candidates else candidates[:1]

    # Prioritize candidates with verified bullish orderflow (buys > sells & positive momentum) ranked by Alpha Score
    bullish_pool = [c for c in pool_to_pick if _has_bullish_orderflow(c)]
    ranked_pool = sorted(bullish_pool if bullish_pool else pool_to_pick, key=_alpha_score, reverse=True)
    pick = random.choice(ranked_pool[: min(2, len(ranked_pool))])

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
            usdc_usd = sum(
                float(t.get("usd_val", 0.0))
                for t in spl_tokens
                if t.get("symbol") == "USDC" or t.get("mint") == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            )
            spl_usd = sum(t.get("usd_val", 0.0) for t in spl_tokens)
            total_live_cash_usd = avail_cash_usd + spl_usd
            avail_cash_idr = total_live_cash_usd * usd_idr

            # Calculate spendable SOL + USDC (reserve priority fee + ATA rent + gas reserve for future sell)
            prio_fee_sol = float(_SNIPER_CONFIG.get("priority_fee_sol", 0.0008))
            needed_gas_reserve_sol = prio_fee_sol + 0.00204 + 0.0020
            sol_bal = float(live_w.balance or 0.0) if live_w else 0.0
            sol_px = live_engine.get_sol_price_usd()
            spendable_sol = max(0.0, sol_bal - needed_gas_reserve_sol)
            spendable_sol_idr = (spendable_sol * sol_px + usdc_usd) * usd_idr
            has_enough_gas = sol_bal >= needed_gas_reserve_sol
        else:
            treasury.ensure_gas_reserve(db, paper_wallet, usd_idr, needed_gas_usd=0.015)
            avail_cash_usd = float(paper_wallet.balance)
            avail_cash_idr = avail_cash_usd * usd_idr
            spendable_sol_idr = avail_cash_idr
            has_enough_gas = True
            needed_gas_reserve_sol = 0.0
            sol_bal = 0.0

        tp_target = float(_SNIPER_CONFIG.get("auto_tp_pct", 12.0))
        sl_target = -abs(float(_SNIPER_CONFIG.get("auto_sl_pct", 8.0)))
        tp_sell_pct = float(_SNIPER_CONFIG.get("auto_tp_sell_pct", 100.0))
        max_positions = max(1, int(_SNIPER_CONFIG.get("max_open_positions", 5)))
        raw_buy_usd = _SNIPER_CONFIG.get("buy_amount_usd")
        cfg_buy_idr = float(_SNIPER_CONFIG.get("buy_amount_idr", 15000.0))
        if raw_buy_usd is not None and float(raw_buy_usd) > 0:
            cfg_buy_usd = round(float(raw_buy_usd), 4)
            cfg_buy_idr = round(cfg_buy_usd * usd_idr, 0)
        else:
            cfg_buy_usd = round(cfg_buy_idr / usd_idr, 4)

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
            if active_mode == "LIVE":
                portfolio.sync_onchain_holdings_to_portfolio(db)
            holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())

        # 0b. Strictly enforce max_open_positions & per-trade dollar cap in PAPER simulation (and LIVE auto-trim)
        if auto_trade and len(holdings) > max_positions:
            for excess_h in list(holdings[max_positions:]):
                try:
                    trim_res = portfolio.sell_holding(db, excess_h.symbol, 100.0, mode=active_mode)
                    state.total_trades = (state.total_trades or 0) + 1
                    db.commit()
                    _append_log(
                        "SNIPE",
                        "SOL",
                        excess_h.symbol,
                        f"[{active_mode} • SLOT LIMIT GUARD] Menjual 100% {excess_h.symbol} agar jumlah posisi aktif patuh batas maksimal ({max_positions} Koin)",
                        f"Kas ({active_mode}): Rp {trim_res['cash_remaining_idr']:,.0f}",
                        "info",
                    )
                except Exception:
                    pass
            holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())

        if active_mode != "LIVE" and auto_trade and cfg_buy_usd > 0:
            for h_chk in list(holdings):
                cost_usd_chk = float(h_chk.quantity or 0.0) * float(h_chk.avg_entry_price or 0.0)
                if cost_usd_chk > (cfg_buy_usd * 1.25):
                    excess_pct = min(95.0, max(10.0, ((cost_usd_chk - cfg_buy_usd) / cost_usd_chk) * 100.0))
                    try:
                        portfolio.sell_holding(db, h_chk.symbol, excess_pct, mode="PAPER")
                        db.commit()
                    except Exception:
                        pass
            holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())
            db.refresh(paper_wallet)
            avail_cash_usd = float(paper_wallet.balance)
            avail_cash_idr = avail_cash_usd * usd_idr
            spendable_sol_idr = avail_cash_idr

        # 1. Refresh live prices on existing holdings & check Auto TP / Trailing Profit / SL
        trailing_enabled = bool(_SNIPER_CONFIG.get("trailing_stop_enabled", True))
        trailing_pct = max(1.5, float(_SNIPER_CONFIG.get("trailing_stop_pct", 3.5)))
        sold_any = False
        for h in holdings:
            pos_key = f"{active_mode}:{h.symbol.upper()}"
            if pos_key not in _HOLDING_ENTRY_TS:
                _HOLDING_ENTRY_TS[pos_key] = now_ts

            if active_mode != "LIVE":
                live_tok = market.resolve_holding_live_price(
                    h.symbol,
                    avg_entry_price=float(h.avg_entry_price or 0.0),
                    current_price=float(h.current_price or 0.0),
                )
                if live_tok and live_tok.get("price", 0) > 0:
                    new_px = float(live_tok["price"])
                    # Guard against unpinned ticker collision inflating a $1 position to $2.9+
                    if h.avg_entry_price > 0 and new_px > (h.avg_entry_price * 2.0) and not market.get_pinned_contract(h.symbol):
                        new_px = float(h.current_price or h.avg_entry_price)
                    h.current_price = new_px
                    if live_tok.get("liquidity", 0) > 0:
                        h.liquidity_usd = float(live_tok["liquidity"])
                    h.updated_at = datetime.now(timezone.utc)
                    db.commit()

            net_m = treasury.compute_holding_net_metrics(h, usd_idr)
            net_pnl_pct = net_m["net_pnl_pct"]
            gross_pnl_pct = net_m["gross_pnl_pct"]

            # Track High-Water Mark Net PnL% for Trailing Profit Lock
            peak_pnl_pct = max(_PEAK_NET_PNL_PCT.get(pos_key, net_pnl_pct), net_pnl_pct)
            _PEAK_NET_PNL_PCT[pos_key] = peak_pnl_pct

            # Trailing Profit Lock: once position reaches >= +4.0% (or 45% of TP target), lock in profit if it pulls back
            trailing_activation_pct = max(3.5, min(6.0, tp_target * 0.45))
            hit_trailing_profit = (
                trailing_enabled
                and peak_pnl_pct >= trailing_activation_pct
                and net_pnl_pct >= 1.2
                and (peak_pnl_pct - net_pnl_pct) >= min(trailing_pct, peak_pnl_pct * 0.45)
            )

            # Grace guard for the first 12 seconds after entry against transient quote spread jitter
            hold_age_sec = max(0.0, now_ts - _HOLDING_ENTRY_TS.get(pos_key, now_ts))
            effective_sl_target = (sl_target * 1.6) if hold_age_sec < 12.0 else sl_target

            hit_tp = net_pnl_pct >= tp_target
            hit_sl = net_pnl_pct <= effective_sl_target
            should_exit = auto_trade and (hit_tp or hit_trailing_profit or hit_sl)

            if should_exit:
                try:
                    sell_pct = tp_sell_pct if (hit_tp or hit_trailing_profit) else 100.0
                    sell_res = portfolio.sell_holding(db, h.symbol, sell_pct, mode=active_mode)
                    state.total_trades = (state.total_trades or 0) + 1
                    db.commit()
                    _PEAK_NET_PNL_PCT.pop(pos_key, None)
                    _HOLDING_ENTRY_TS.pop(pos_key, None)
                    if hit_tp:
                        reason = f"AUTO TAKE-PROFIT [{strat_mode}]"
                    elif hit_trailing_profit:
                        reason = f"AUTO TRAILING-PROFIT [{strat_mode} • Peak +{peak_pnl_pct:.1f}%]"
                    else:
                        reason = f"AUTO STOP-LOSS [{strat_mode}]"
                        sym_u = h.symbol.upper()
                        base_u = sym_u.split("/")[0]
                        _RECENT_SL_COOLDOWN[sym_u] = now_ts
                        _RECENT_SL_COOLDOWN[base_u] = now_ts

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
                except Exception as sell_err:
                    _append_log(
                        "SYSTEM",
                        "SOL",
                        h.symbol,
                        f"⚠️ Gagal/Tunda eksekusi jual {h.symbol}: {sell_err}",
                        "",
                        "warn",
                    )

        # 2. Auto-Snipe new token if we have sufficient spendable Cash and open positions < max_positions
        score_threshold = (min_score - 15) if strat_mode == "AGGRESSIVE" else (min_score - 5)
        min_cash_threshold = max(2000.0, cfg_buy_idr)
        has_enough_cash = (spendable_sol_idr >= min_cash_threshold and has_enough_gas) if active_mode == "LIVE" else (avail_cash_idr >= min_cash_threshold)

        # Re-verify that pick is NOT already held and open holdings count is strictly < max_positions
        holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())
        held_symbols = {h.symbol.upper() for h in holdings}
        held_bases = {h.symbol.upper().split("/")[0] for h in holdings}

        can_snipe = (
            not sold_any
            and auto_trade
            and has_unheld_candidate
            and _not_held(pick)
            and has_enough_cash
            and len(holdings) < max_positions
            and score >= score_threshold
            and (force_trade or _has_bullish_orderflow(pick) or bool(bullish_pool))
        )

        if can_snipe:
            if active_mode == "LIVE":
                # Adapt buy size to available spendable SOL cash, bounded by cfg_buy_idr
                snipe_idr = min(cfg_buy_idr, max(2000.0, spendable_sol_idr))
            else:
                # Obey operator configured buy amount, bounded by available paper cash
                snipe_idr = min(cfg_buy_idr, avail_cash_idr)
            snipe_usd = round(min(cfg_buy_usd, snipe_idr / usd_idr), 4)
            try:
                snipe_res = memecoins.execute_snipe(
                    db,
                    {
                        "symbol": sym,
                        "contract": contract_addr,
                        "price": price_usd,
                        "amount_usd": snipe_usd,
                        "amount_idr": snipe_idr,
                        "slippage_pct": float(_SNIPER_CONFIG.get("slippage_pct", 1.0)),
                        "priority_fee_sol": float(_SNIPER_CONFIG.get("priority_fee_sol", 0.005)),
                        "anti_mev": bool(_SNIPER_CONFIG.get("anti_mev", True)),
                        "force_unsafe": strat_mode == "AGGRESSIVE",
                        "block_legacy_tokens": strat_mode == "AGGRESSIVE",
                        "mode": active_mode,
                        "from_bot": True,
                        "max_open_positions": max_positions,
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
                if active_mode == "LIVE":
                    if not has_enough_gas:
                        skip_reason = f"Gas SOL ({sol_bal:.6f} SOL) < batas cadangan aman ({needed_gas_reserve_sol:.4f} SOL). Menahan beli agar gas cukup untuk jual & tidak gantung."
                    else:
                        skip_reason = f"SOL Kas Rp {spendable_sol_idr:,.0f} < batas minimal beli Rp {min_cash_threshold:,.0f}"
                else:
                    skip_reason = f"Kas Paper Rp {avail_cash_idr:,.0f} < batas minimal beli Rp {min_cash_threshold:,.0f}"
            elif len(holdings) >= max_positions:
                skip_reason = f"Slot open positions penuh ({len(holdings)}/{max_positions})"
            elif score < score_threshold:
                skip_reason = f"Skor Keamanan {score:.0f} di bawah batas minimal {score_threshold:.0f} [{strat_mode}] (Anti-Rug Guard aktif)"

            ov = portfolio.get_overview(db, refresh_live_prices=True, mode=active_mode)
            holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)).scalars().all())
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

    res_payload = {
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
    _LAST_TICK_RESULT = res_payload
    return res_payload


def get_bot_activity(db: Session, tick: bool = True, force_trade: bool = False) -> dict:
    _load_persisted_sniper_config()
    state = get_bot_status(db)
    if (tick or force_trade) and state.status == "running":
        return run_bot_scan_tick(db, auto_trade=True, force_trade=force_trade)
    fx = market.get_fx_rate()
    strat_mode = (_SNIPER_CONFIG.get("strategy_mode") or "AGGRESSIVE").upper()
    return {
        "status": state.status,
        "mode": state.mode,
        "strategy_mode": strat_mode,
        "total_trades": state.total_trades or 0,
        "sniper_config": get_sniper_config(),
        "current_stage": _CURRENT_STAGE,
        "logs": _BOT_ACTIVITY_LOGS[:25],
        "usd_idr": fx["usd_idr"],
        "trade_executed": False,
    }

