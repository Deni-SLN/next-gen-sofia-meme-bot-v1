import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services import market, memecoins

logger = logging.getLogger("auto_entry")

_STATE_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "auto_entry_state.json"
_LOCK = threading.RLock()
_TICK_LOCK = threading.Lock()
_DAEMON_THREAD: Optional[threading.Thread] = None

_DEFAULT_STATE: dict[str, Any] = {
    "status": "STOPPED",  # STOPPED | RUNNING | QUOTA_REACHED
    "mode": "PAPER",      # PAPER | LIVE
    "entry_amount_idr": 20000.0,
    "entry_amount_usd": 1.10,
    "max_entries": 5,
    "slippage_pct": 1.0,
    "min_safety_score": 70,
    "target_source": "ALL_RADAR",  # ALL_RADAR | NEW_CREATIONS | FINAL_STRETCH | MIGRATED
    "total_entries_count": 0,
    "total_spent_idr": 0.0,
    "total_spent_usd": 0.0,
    "current_scanning_candidate": None,
    "last_scan_time": None,
    "last_entry_time": None,
    "entries_history": [],
    "scan_logs": [],
    "updated_at": None,
}

_STATE: dict[str, Any] = {}


def _load_persisted_state() -> None:
    global _STATE
    if _STATE:
        return
    try:
        if _STATE_FILE_PATH.exists():
            data = json.loads(_STATE_FILE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = _DEFAULT_STATE.copy()
                merged.update(data)
                _STATE = merged
                return
    except Exception as exc:
        logger.warning(f"Failed to load auto_entry_state.json: {exc}")
    _STATE = _DEFAULT_STATE.copy()


def _save_persisted_state() -> None:
    try:
        _STATE["updated_at"] = datetime.now(timezone.utc).isoformat()
        _STATE_FILE_PATH.write_text(json.dumps(_STATE, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to save auto_entry_state.json: {exc}")


def _append_log(badge: str, token: str, message: str, level: str = "info") -> None:
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = {
        "id": f"{int(time.time() * 1000)}-{len(_STATE.get('scan_logs', []))}",
        "time": now_str,
        "badge": badge,  # SCAN | AUDIT | ENTRY | QUOTA | SYSTEM
        "token": token,
        "message": message,
        "level": level,  # info | success | warn | danger
    }
    logs = _STATE.setdefault("scan_logs", [])
    logs.insert(0, entry)
    if len(logs) > 80:
        logs.pop()


def get_auto_entry_state() -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        return json.loads(json.dumps(_STATE))


def update_auto_entry_config(params: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        if "entry_amount_idr" in params and params["entry_amount_idr"] is not None:
            val = max(1000.0, float(params["entry_amount_idr"]))
            _STATE["entry_amount_idr"] = val
            fx_val = float(market.get_fx_rate().get("usd_idr") or 16500.0)
            _STATE["entry_amount_usd"] = round(val / fx_val, 4) if fx_val > 0 else 1.0

        if "entry_amount_usd" in params and params["entry_amount_usd"] is not None:
            val_usd = max(0.1, float(params["entry_amount_usd"]))
            _STATE["entry_amount_usd"] = val_usd
            fx_val = float(market.get_fx_rate().get("usd_idr") or 16500.0)
            _STATE["entry_amount_idr"] = round(val_usd * fx_val, 0)

        if "max_entries" in params and params["max_entries"] is not None:
            _STATE["max_entries"] = max(1, min(50, int(params["max_entries"])))

        if "slippage_pct" in params and params["slippage_pct"] is not None:
            _STATE["slippage_pct"] = max(0.1, min(25.0, float(params["slippage_pct"])))

        if "min_safety_score" in params and params["min_safety_score"] is not None:
            _STATE["min_safety_score"] = max(0, min(100, int(params["min_safety_score"])))

        if "mode" in params and params["mode"]:
            m = str(params["mode"]).upper()
            if m in ("PAPER", "LIVE"):
                _STATE["mode"] = m

        if "target_source" in params and params["target_source"]:
            _STATE["target_source"] = str(params["target_source"]).upper()

        _save_persisted_state()
        return json.loads(json.dumps(_STATE))


def start_auto_entry(params: Optional[dict[str, Any]] = None, db: Optional[Session] = None) -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        if params:
            update_auto_entry_config(params)

        # Check if already reached max entries
        if _STATE["total_entries_count"] >= _STATE["max_entries"]:
            _STATE["status"] = "QUOTA_REACHED"
            _append_log(
                "QUOTA",
                "SYSTEM",
                f"Batas maksimal entry sudah terpenuhi ({_STATE['total_entries_count']}/{_STATE['max_entries']}). Reset kuota untuk memulai kembali.",
                "warn",
            )
        else:
            _STATE["status"] = "RUNNING"
            _append_log(
                "SYSTEM",
                "AUTO_ENTRY",
                f"Bot Auto Entry AKTIF. Target: {_STATE['max_entries']} entry @ Rp {_STATE['entry_amount_idr']:,.0f} (Slippage: {_STATE['slippage_pct']}%, Min Score: {_STATE['min_safety_score']}).",
                "success",
            )

        _save_persisted_state()

    ensure_auto_entry_daemon()
    return get_auto_entry_state()


def stop_auto_entry() -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        _STATE["status"] = "STOPPED"
        _STATE["current_scanning_candidate"] = None
        _append_log("SYSTEM", "AUTO_ENTRY", "Bot Auto Entry DIHENTIKAN oleh pengguna.", "warn")
        _save_persisted_state()
        return json.loads(json.dumps(_STATE))


def reset_auto_entry_counter() -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        _STATE["total_entries_count"] = 0
        _STATE["total_spent_idr"] = 0.0
        _STATE["total_spent_usd"] = 0.0
        _STATE["entries_history"] = []
        _STATE["current_scanning_candidate"] = None
        if _STATE["status"] == "QUOTA_REACHED":
            _STATE["status"] = "RUNNING"
        _append_log("SYSTEM", "COUNTER", "Counter entry dan riwayat sesi telah di-reset ke 0.", "info")
        _save_persisted_state()
        return json.loads(json.dumps(_STATE))


def _execute_auto_entry_tick(db: Session) -> dict[str, Any]:
    """Single tick scanning and entry acquisition cycle with concurrency lock."""
    if not _TICK_LOCK.acquire(blocking=False):
        return {"status": "BUSY", "action": "tick_in_progress"}
    try:
        return _execute_auto_entry_tick_inner(db)
    finally:
        _TICK_LOCK.release()


def _execute_auto_entry_tick_inner(db: Session) -> dict[str, Any]:
    with _LOCK:
        _load_persisted_state()
        status = _STATE.get("status", "STOPPED")
        if status != "RUNNING":
            return {"status": status, "action": "idle"}

        total_count = _STATE.get("total_entries_count", 0)
        max_entries = _STATE.get("max_entries", 5)

        if total_count >= max_entries:
            _STATE["status"] = "QUOTA_REACHED"
            _STATE["current_scanning_candidate"] = None
            _append_log(
                "QUOTA",
                "SYSTEM",
                f"Batas maksimal entry ({max_entries}/{max_entries}) telah tercapai! Auto Entry selesai.",
                "success",
            )
            _save_persisted_state()
            return {"status": "QUOTA_REACHED", "action": "quota_reached"}

        mode = _STATE.get("mode", "PAPER")
        entry_idr = float(_STATE.get("entry_amount_idr", 20000.0))
        slippage = float(_STATE.get("slippage_pct", 1.0))
        min_score = int(_STATE.get("min_safety_score", 70))
        target_src = _STATE.get("target_source", "ALL_RADAR")

    # Fetch fresh candidate pool from pulse radar
    try:
        pulse_data = memecoins.get_pulse_feed()
    except Exception as exc:
        logger.warning(f"Auto entry failed to fetch pulse: {exc}")
        return {"status": "RUNNING", "action": "pulse_error"}

    new_cr = pulse_data.get("new_creations", [])
    final_st = pulse_data.get("final_stretch", [])
    migrated = pulse_data.get("migrated", [])

    if target_src == "NEW_CREATIONS":
        candidates = new_cr
    elif target_src == "FINAL_STRETCH":
        candidates = final_st
    elif target_src == "MIGRATED":
        candidates = migrated
    else:
        candidates = new_cr + final_st + migrated

    with _LOCK:
        entered_contracts = {
            e.get("contract") for e in _STATE.get("entries_history", []) if e.get("contract")
        }
        entered_symbols = {
            e.get("symbol") for e in _STATE.get("entries_history", []) if e.get("symbol")
        }

    # Filter candidate:
    # 1. Not already entered in this session
    # 2. Safety score >= min_score
    # 3. Not a legacy or charity/donasi/mayhem token
    # 4. Anti-Honeypot & Contract Security pre-filter
    eligible = []
    for c in candidates:
        sym = c.get("symbol") or c.get("base_symbol") or ""
        ca = c.get("contract") or ""
        score = int(c.get("safety_score", 0))
        if sym in entered_symbols or ca in entered_contracts:
            continue
        if score < min_score:
            continue
        if market.is_legacy_token(sym) or c.get("is_charity") or market.is_charity_token(sym, c.get("name")):
            continue
        if c.get("honeypot") is True:
            continue
        if c.get("mint_revoked") is False or c.get("freeze_revoked") is False:
            continue
        buys_5m = int(c.get("buys_5m") or 0)
        sells_5m = int(c.get("sells_5m") or 0)
        if buys_5m >= 12 and sells_5m == 0:
            # Sell-blocked honeypot pattern
            continue
        eligible.append(c)

    if not eligible:
        with _LOCK:
            _STATE["last_scan_time"] = datetime.now(timezone.utc).isoformat()
            if candidates:
                cand = candidates[0]
                _STATE["current_scanning_candidate"] = {
                    "symbol": cand.get("symbol"),
                    "name": cand.get("name"),
                    "contract": cand.get("contract"),
                    "safety_score": cand.get("safety_score"),
                    "liquidity": cand.get("liquidity"),
                    "price": cand.get("price"),
                    "launchpad": cand.get("launchpad"),
                }
            _save_persisted_state()
        return {"status": "RUNNING", "action": "no_eligible_candidate"}

    # Pick candidate with highest safety score & liquidity
    eligible.sort(key=lambda x: (int(x.get("safety_score", 0)), float(x.get("liquidity", 0))), reverse=True)
    pick = eligible[0]

    pick_sym = pick.get("symbol") or pick.get("base_symbol") or "TOKEN"
    pick_ca = pick.get("contract") or ""
    pick_score = int(pick.get("safety_score", 0))

    with _LOCK:
        _STATE["current_scanning_candidate"] = {
            "symbol": pick_sym,
            "name": pick.get("name", pick_sym),
            "contract": pick_ca,
            "safety_score": pick_score,
            "liquidity": pick.get("liquidity"),
            "price": pick.get("price"),
            "launchpad": pick.get("launchpad"),
        }
        _append_log(
            "AUDIT",
            pick_sym,
            f"Kandidat terpilih lolos filter awal: {pick_sym} (Score {pick_score}/100 • Liq ${pick.get('liquidity', 0):,.0f}). Memverifikasi Anti-Honeypot On-Chain...",
            "info",
        )

    # Deep On-Chain Anti-Honeypot & Contract Security Audit via FluxRPC Shield + RugCheck
    try:
        live_audit = market.live_rug_audit(pick_ca or pick_sym)
        if (
            live_audit.get("honeypot") is True
            or not live_audit.get("contract_clean", True)
            or int(live_audit.get("safety_score", 0)) < min_score
        ):
            reason = live_audit.get("verdict") or "Terdeteksi potensi Honeypot / Kontrak Berbahaya"
            with _LOCK:
                _append_log(
                    "SECURITY",
                    pick_sym,
                    f"[ANTI-HONEYPOT] Entry {pick_sym} DIBATALKAN demi keamanan modal: {reason}",
                    "danger",
                )
                _save_persisted_state()
            return {"status": "RUNNING", "action": "blocked_by_security_shield", "reason": reason}
    except Exception:
        pass

    # Execute Entry Snipe
    try:
        snipe_res = memecoins.execute_snipe(
            db,
            {
                "symbol": pick_sym,
                "contract": pick_ca,
                "amount_idr": entry_idr,
                "slippage_pct": slippage,
                "mode": mode,
                "anti_mev": True,
                "priority_fee_sol": 0.001,
            },
        )
    except Exception as exc:
        err_msg = str(exc)
        with _LOCK:
            _append_log("WARN", pick_sym, f"Gagal mengeksekusi entry pada {pick_sym}: {err_msg}", "danger")
            _save_persisted_state()
        return {"status": "RUNNING", "action": "snipe_failed", "error": err_msg}

    # Record filled entry
    now_iso = datetime.now(timezone.utc).isoformat()
    spent_idr = float(snipe_res.get("amount_idr") or entry_idr)
    spent_usd = float(snipe_res.get("amount_usd") or (spent_idr / 16500.0))

    entry_record = {
        "id": f"entry-{int(time.time() * 1000)}",
        "timestamp": now_iso,
        "symbol": pick_sym,
        "name": pick.get("name", pick_sym),
        "contract": pick_ca,
        "wallet_address": snipe_res.get("wallet_address") or snipe_res.get("wallet_name") or "Primary Trading Wallet",
        "entry_price": snipe_res.get("entry_price"),
        "entry_price_idr": snipe_res.get("entry_price_idr"),
        "quantity": snipe_res.get("quantity"),
        "amount_idr": spent_idr,
        "amount_usd": spent_usd,
        "slippage_pct": snipe_res.get("slippage_pct") or slippage,
        "safety_score": pick_score,
        "mode": mode,
        "tx_hash": snipe_res.get("tx_hash") or "SIMULATED_FILLED",
        "launchpad": pick.get("launchpad", "Raydium"),
    }

    with _LOCK:
        _STATE["total_entries_count"] += 1
        _STATE["total_spent_idr"] += spent_idr
        _STATE["total_spent_usd"] += spent_usd
        _STATE["last_entry_time"] = now_iso
        _STATE["entries_history"].insert(0, entry_record)

        new_total = _STATE["total_entries_count"]
        max_ent = _STATE["max_entries"]

        _append_log(
            "ENTRY",
            pick_sym,
            f"⚡ Berhasil Auto Entry {pick_sym} senilai Rp {spent_idr:,.0f} (${spent_usd:.2f}) @ ${entry_record['entry_price']:.6f}. Posisi: {new_total}/{max_ent}",
            "success",
        )

        if new_total >= max_ent:
            _STATE["status"] = "QUOTA_REACHED"
            _STATE["current_scanning_candidate"] = None
            _append_log(
                "QUOTA",
                "SYSTEM",
                f"Batas maksimal entry tercapai ({new_total}/{max_ent}). Pemindaian otomatis dihentikan.",
                "success",
            )

        _save_persisted_state()

    return {
        "status": _STATE["status"],
        "action": "entry_filled",
        "entry": entry_record,
        "counter": f"{_STATE['total_entries_count']}/{_STATE['max_entries']}",
    }


def trigger_manual_scan_tick(db: Session) -> dict[str, Any]:
    return _execute_auto_entry_tick(db)


def compute_profit_potential(token: dict[str, Any]) -> dict[str, Any]:
    """Compute calculated profit potential score (0-100), grade, upside, and catalyst drivers."""
    score = 52.0
    catalysts = []

    # 1. Buy pressure vs sell pressure
    buys = float(token.get("buys_5m") or 0)
    sells = float(token.get("sells_5m") or 0)
    if (buys + sells) > 0:
        buy_ratio = buys / (buys + sells)
        diff = (buy_ratio - 0.5) * 32.0
        score += diff
        if buy_ratio >= 0.65:
            catalysts.append(f"Inflow Dominan ({int(buy_ratio * 100)}% Buys)")

    # 2. Price momentum (5m, 1h, 24h)
    chg_5m = float(token.get("price_change_5m") or 0)
    chg_1h = float(token.get("price_change_1h") or 0)
    chg_24h = float(token.get("price_change_24h") or 0)

    if chg_5m > 0:
        score += min(14.0, chg_5m * 0.7)
        catalysts.append(f"Momentum 5m +{chg_5m:.1f}%")
    if chg_1h > 0:
        score += min(10.0, chg_1h * 0.25)
    if chg_24h > 30:
        catalysts.append(f"Reli 24h +{chg_24h:.0f}%")

    # 3. Volume to liquidity turnover
    vol = float(token.get("volume_24h") or token.get("volume_5m") or 0)
    liq = max(500.0, float(token.get("liquidity") or 500.0))
    vol_liq_ratio = vol / liq
    if vol_liq_ratio >= 1.5:
        score += min(12.0, vol_liq_ratio * 1.8)
        catalysts.append(f"Vol/Liq {vol_liq_ratio:.1f}x Tinggi")

    # 4. Smart Money Degens & GMGN tracking
    degens = int(token.get("gmgn_smart_degens") or 0)
    if degens > 0:
        score += min(16.0, degens * 3.5)
        catalysts.append(f"{degens} Smart Money Terdeteksi")

    # 5. Bonding curve stage
    curve_pct = float(token.get("bonding_curve_pct") or 0)
    if 50.0 <= curve_pct < 95.0:
        score += 8.0
        catalysts.append(f"Bonding Curve {curve_pct:.0f}% (Akumulasi Aktif)")

    final_score = int(max(38, min(99, round(score))))

    if final_score >= 85:
        grade = "A+"
        label = "Super Cuan"
        upside = "3x - 10x Potential"
    elif final_score >= 75:
        grade = "A"
        label = "Peluang Tinggi"
        upside = "2x - 5x Potential"
    elif final_score >= 65:
        grade = "B+"
        label = "Potensial"
        upside = "50% - 150% Scalp"
    else:
        grade = "B"
        label = "Moderat"
        upside = "20% - 50% Momentum"

    if not catalysts:
        catalysts = ["Volume Aktif di DEX", "Likuiditas Terverifikasi"]

    return {
        "profit_score": final_score,
        "profit_grade": grade,
        "profit_label": label,
        "estimated_upside": upside,
        "catalysts": catalysts[:3],
    }


def get_scanned_memecoins(
    min_safety: int = 60,
    min_profit: int = 50,
    sort_by: str = "cuan",
    target_pool: str = "ALL",
) -> dict[str, Any]:
    """
    Fetch and analyze meme coins across Solana pools filtered by Profit Potential and Safety Scores.
    Each token includes full CA address for 1-click copy and rapid auto-entry execution.
    """
    try:
        pulse = memecoins.get_pulse_feed()
    except Exception as exc:
        logger.warning(f"Failed to fetch pulse in get_scanned_memecoins: {exc}")
        pulse = {}

    all_raw: list[dict[str, Any]] = []
    pool_filter = (target_pool or "ALL").upper()

    if pool_filter in ("ALL", "NEW_CREATIONS"):
        for item in pulse.get("new_creations", []):
            item_copy = dict(item)
            item_copy["category"] = "NEW_CREATIONS"
            all_raw.append(item_copy)

    if pool_filter in ("ALL", "FINAL_STRETCH"):
        for item in pulse.get("final_stretch", []):
            item_copy = dict(item)
            item_copy["category"] = "FINAL_STRETCH"
            all_raw.append(item_copy)

    if pool_filter in ("ALL", "MIGRATED"):
        for item in pulse.get("migrated", []):
            item_copy = dict(item)
            item_copy["category"] = "MIGRATED"
            all_raw.append(item_copy)

    seen = set()
    enriched: list[dict[str, Any]] = []

    for t in all_raw:
        sym = t.get("symbol") or t.get("base_symbol") or ""
        ca = t.get("contract") or ""
        key = ca if len(ca) >= 20 else sym
        if not key or key in seen:
            continue
        seen.add(key)

        if market.is_legacy_token(sym) or t.get("is_charity") or market.is_charity_token(sym, t.get("name")):
            continue

        profit_meta = compute_profit_potential(t)
        safety_score = int(t.get("safety_score") or 70)

        # Safety badges
        audit_badges = []
        if t.get("mint_revoked"):
            audit_badges.append("Mint Revoked")
        if t.get("lp_burned") or float(t.get("lp_locked_pct") or 0) > 80:
            audit_badges.append("LP Burned/Locked")
        if float(t.get("top10_pct") or 100) <= 25.0:
            audit_badges.append("Top 10 Sehat")
        if float(t.get("dev_holding_pct") or 100) <= 5.0:
            audit_badges.append("Dev Holding Aman")

        composite_score = round(profit_meta["profit_score"] * 0.55 + safety_score * 0.45, 1)

        # Apply minimum filters
        if safety_score < min_safety or profit_meta["profit_score"] < min_profit:
            continue

        enriched.append({
            "symbol": sym,
            "base_symbol": t.get("base_symbol") or sym.split("/")[0],
            "name": t.get("name") or sym,
            "contract": ca,
            "chain": t.get("chain", "Solana"),
            "dex": t.get("dex", "Raydium"),
            "launchpad": t.get("launchpad", "Pump.fun"),
            "price": float(t.get("price") or 0.0),
            "price_idr": float(t.get("price_idr") or 0.0),
            "price_change_5m": float(t.get("price_change_5m") or 0.0),
            "price_change_1h": float(t.get("price_change_1h") or 0.0),
            "price_change_24h": float(t.get("price_change_24h") or 0.0),
            "volume_24h": float(t.get("volume_24h") or 0.0),
            "volume_5m": float(t.get("volume_5m") or 0.0),
            "liquidity": float(t.get("liquidity") or 0.0),
            "liquidity_idr": float(t.get("liquidity_idr") or 0.0),
            "market_cap": float(t.get("market_cap") or 0.0),
            "buys_5m": int(t.get("buys_5m") or 0),
            "sells_5m": int(t.get("sells_5m") or 0),
            "holders": int(t.get("holders") or 0),
            "age": t.get("age", "1h"),
            "bonding_curve_pct": float(t.get("bonding_curve_pct") or 0.0),
            "gmgn_smart_degens": int(t.get("gmgn_smart_degens") or 0),
            "category": t.get("category", "NEW_CREATIONS"),
            "dex_url": t.get("dex_url") or f"https://dexscreener.com/solana/{ca}",
            # Profit metrics
            "profit_score": profit_meta["profit_score"],
            "profit_grade": profit_meta["profit_grade"],
            "profit_label": profit_meta["profit_label"],
            "estimated_upside": profit_meta["estimated_upside"],
            "catalysts": profit_meta["catalysts"],
            # Safety metrics
            "safety_score": safety_score,
            "composite_score": composite_score,
            "audit_badges": audit_badges,
            "mint_revoked": bool(t.get("mint_revoked")),
            "lp_burned": bool(t.get("lp_burned")),
            "top10_pct": float(t.get("top10_pct") or 0.0),
            "dev_holding_pct": float(t.get("dev_holding_pct") or 0.0),
        })

    # Sorting
    if sort_by == "safety":
        enriched.sort(key=lambda x: (x["safety_score"], x["profit_score"], x["liquidity"]), reverse=True)
    elif sort_by == "composite":
        enriched.sort(key=lambda x: (x["composite_score"], x["liquidity"]), reverse=True)
    elif sort_by == "volume":
        enriched.sort(key=lambda x: (x["volume_24h"], x["profit_score"]), reverse=True)
    else:  # default 'cuan'
        enriched.sort(key=lambda x: (x["profit_score"], x["safety_score"], x["volume_24h"]), reverse=True)

    high_cuan = sum(1 for x in enriched if x["profit_score"] >= 80)
    high_safe = sum(1 for x in enriched if x["safety_score"] >= 75)

    return {
        "tokens": enriched,
        "total_scanned": len(enriched),
        "high_potential_count": high_cuan,
        "high_safety_count": high_safe,
        "filter_applied": {
            "min_safety": min_safety,
            "min_profit": min_profit,
            "sort_by": sort_by,
            "target_pool": pool_filter,
        },
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


def execute_single_token_auto_entry(
    db: Session,
    contract: str,
    symbol: Optional[str] = None,
    name: Optional[str] = None,
) -> dict[str, Any]:
    """Execute rapid single-token auto entry directly from the scanner view."""
    with _LOCK:
        _load_persisted_state()
        token_symbol = symbol or "TOKEN"
        token_name = name or token_symbol

        # Strict block on charity / donation tokens
        if market.is_charity_token(token_symbol, token_name):
            _append_log("BLOCKED", token_symbol, "Auto Entry ditolak: Koin amal / charity dilarang oleh filter kebijakan Sofia Trade.", "danger")
            _save_persisted_state()
            return {
                "success": False,
                "error": f"Eksekusi dibatalkan: Token {token_symbol} terindikasi sebagai koin amal / charity yang dilarang oleh filter keamanan Sofia Trade Engine.",
            }

        total_count = _STATE.get("total_entries_count", 0)
        max_entries = _STATE.get("max_entries", 5)

        if total_count >= max_entries:
            return {
                "success": False,
                "error": f"Batas kuota maksimal entry ({max_entries}/{max_entries}) sudah terpenuhi. Silakan reset kuota.",
                "quota_reached": True,
            }

        mode = _STATE.get("mode", "PAPER")
        entry_idr = float(_STATE.get("entry_amount_idr", 20000.0))
        slippage = float(_STATE.get("slippage_pct", 1.0))

    try:
        snipe_res = memecoins.execute_snipe(
            db,
            {
                "symbol": token_symbol,
                "contract": contract,
                "amount_idr": entry_idr,
                "slippage_pct": slippage,
                "mode": mode,
                "anti_mev": True,
                "priority_fee_sol": 0.001,
            },
        )
    except Exception as exc:
        err_msg = str(exc)
        with _LOCK:
            _append_log("WARN", token_symbol, f"Gagal Auto Entry koin {token_symbol}: {err_msg}", "danger")
            _save_persisted_state()
        return {"success": False, "error": err_msg}

    now_iso = datetime.now(timezone.utc).isoformat()
    spent_idr = float(snipe_res.get("amount_idr") or entry_idr)
    spent_usd = float(snipe_res.get("amount_usd") or (spent_idr / 16500.0))

    entry_record = {
        "id": f"entry-{int(time.time() * 1000)}",
        "timestamp": now_iso,
        "symbol": token_symbol,
        "name": token_name,
        "contract": contract,
        "wallet_address": snipe_res.get("wallet_address") or snipe_res.get("wallet_name") or "Primary Trading Wallet",
        "entry_price": snipe_res.get("entry_price"),
        "entry_price_idr": snipe_res.get("entry_price_idr"),
        "quantity": snipe_res.get("quantity"),
        "amount_idr": spent_idr,
        "amount_usd": spent_usd,
        "slippage_pct": snipe_res.get("slippage_pct") or slippage,
        "safety_score": snipe_res.get("safety_score") or 75,
        "mode": mode,
        "tx_hash": snipe_res.get("tx_hash") or "SIMULATED_FILLED",
        "launchpad": snipe_res.get("launchpad", "Raydium"),
    }

    with _LOCK:
        _STATE["total_entries_count"] += 1
        _STATE["total_spent_idr"] += spent_idr
        _STATE["total_spent_usd"] += spent_usd
        _STATE["last_entry_time"] = now_iso
        _STATE["entries_history"].insert(0, entry_record)

        new_total = _STATE["total_entries_count"]
        max_ent = _STATE["max_entries"]

        _append_log(
            "ENTRY",
            token_symbol,
            f"⚡ [Mode Scan] Auto Entry {token_symbol} senilai Rp {spent_idr:,.0f} (${spent_usd:.2f}) @ ${entry_record['entry_price']:.6f}. Posisi: {new_total}/{max_ent}",
            "success",
        )

        if new_total >= max_ent:
            _STATE["status"] = "QUOTA_REACHED"
            _STATE["current_scanning_candidate"] = None
            _append_log(
                "QUOTA",
                "SYSTEM",
                f"Batas maksimal entry tercapai ({new_total}/{max_ent}). Auto Entry dijeda.",
                "success",
            )

        _save_persisted_state()

    return {
        "success": True,
        "entry": entry_record,
        "counter": f"{_STATE['total_entries_count']}/{_STATE['max_entries']}",
        "quota_reached": _STATE["status"] == "QUOTA_REACHED",
    }


def ensure_auto_entry_daemon() -> None:
    """Daemon worker is managed asynchronously by main application lifespan worker."""
    pass
