from datetime import datetime, timezone
import threading
import time
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Wallet
from app.services import market, portfolio, treasury


_SPL_TTL_SECONDS = 60.0
_BG_SYNC_LOCK = threading.Lock()
_BG_SYNC_RUNNING = False
DEFAULT_USER_SOLANA_WALLET = "8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos"


def get_or_ensure_primary_solana_wallet(db: Session) -> Wallet:
    """Return the user's primary Solana wallet recorded in system settings (defaulting to 8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos)."""
    w = (
        db.execute(
            select(Wallet)
            .where(
                Wallet.chain == "Solana",
                Wallet.gate == "trading",
                ~Wallet.name.contains("Modal Paper"),
            )
            .order_by(Wallet.id.asc())
        )
        .scalars()
        .first()
    )
    if not w:
        w = Wallet(
            name="Dompet Utama Solana (Pengaturan Sistem)",
            address=DEFAULT_USER_SOLANA_WALLET,
            chain="Solana",
            balance=0.0,
            token="SOL",
            gate="trading",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(w)
        db.commit()
        db.refresh(w)
    elif not w.address or w.address == "BYyj6C1tykoREhVFQKbmoNc6axT1tUrdMNZZT6XHoYZ8":
        w.address = DEFAULT_USER_SOLANA_WALLET
        w.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(w)
    return w


def set_primary_solana_wallet(db: Session, address: str, name: str | None = None) -> dict:
    """Update or create the primary Solana wallet from System Settings & Credentials and sync on-chain."""
    clean_addr = (address or "").strip() or DEFAULT_USER_SOLANA_WALLET
    w = get_or_ensure_primary_solana_wallet(db)
    w.address = clean_addr
    if name:
        w.name = name.strip()
    w.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(w)
    _trigger_bg_onchain_wallet_sync(clean_addr)
    fx = market.get_fx_rate()
    return _wallet_to_dict(w, fx["usd_idr"])


def _trigger_bg_onchain_wallet_sync(trading_addr: str | None = None) -> None:
    """Refresh on-chain SOL and SPL balances in a background thread so GET /api/v1/wallets never blocks UI navigation."""
    global _BG_SYNC_RUNNING
    with _BG_SYNC_LOCK:
        if _BG_SYNC_RUNNING:
            return
        _BG_SYNC_RUNNING = True

    def _worker() -> None:
        global _BG_SYNC_RUNNING
        try:
            from app.db.session import SessionLocal
            from app.services import live_engine

            with SessionLocal() as bg_db:
                live_engine.auto_sync_live_wallets(bg_db, max_age_seconds=_SPL_TTL_SECONDS)
            if trading_addr:
                live_engine.query_solana_spl_tokens(trading_addr, max_cache_seconds=_SPL_TTL_SECONDS)
        except Exception:
            pass
        finally:
            with _BG_SYNC_LOCK:
                _BG_SYNC_RUNNING = False

    threading.Thread(target=_worker, name="sofia-wallet-bg-sync", daemon=True).start()


def _wallet_to_dict(w: Wallet, usd_idr: float) -> dict:
    from app.services import live_engine
    token_upper = (w.token or "USDT").upper()
    if "SOL" in token_upper and "USD" not in token_upper:
        sol_info = market.get_live_token_info("SOL/USDT", max_cache_age=300.0)
        sol_price = float(sol_info["price"]) if (sol_info and sol_info.get("price", 0) > 10) else 145.0
        native_usd = w.balance * sol_price
    else:
        native_usd = w.balance

    spl_tokens = []
    usdc_bal = 0.0
    usdc_usd = 0.0
    if w.chain == "Solana" and w.address and w.gate == "trading" and "Modal Paper" not in (w.name or ""):
        addr = w.address.strip()
        cached_entry = live_engine._SPL_CACHE.get(addr)
        if cached_entry is not None:
            cache_ts, spl_tokens = cached_entry
            if (time.time() - cache_ts) > _SPL_TTL_SECONDS:
                _trigger_bg_onchain_wallet_sync(addr)
        else:
            _trigger_bg_onchain_wallet_sync(addr)
        for t in spl_tokens:
            if t.get("symbol") == "USDC" or t.get("mint") == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":
                usdc_bal += float(t.get("amount") or 0.0)
                usdc_usd += float(t.get("usd_val") or 0.0)

    cash_usd = native_usd + usdc_usd
    total_val = native_usd + sum(t.get("usd_val", 0.0) for t in spl_tokens)

    return {
        "id": w.id,
        "name": w.name,
        "address": w.address,
        "chain": w.chain,
        "balance": round(w.balance, 6),
        "balance_usd": round(cash_usd, 2),
        "balance_idr": round(cash_usd * usd_idr, 0),
        "total_equity_usd": round(total_val, 2),
        "token": w.token,
        "gate": w.gate,
        "usdc_balance": round(usdc_bal, 4),
        "usdc_usd": round(usdc_usd, 4),
        "usdc_idr": round(usdc_usd * usd_idr, 0),
        "gas_fee_balance": round(w.balance, 6),
        "gas_fee_token": w.token,
        "gas_fee_usd": round(native_usd, 4),
        "gas_fee_idr": round(native_usd * usd_idr, 0),
        "spl_tokens": spl_tokens,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def list_wallets(db: Session) -> dict:
    from app.services import live_engine

    if (time.time() - getattr(live_engine, "_LAST_ONCHAIN_SYNC", 0.0)) >= _SPL_TTL_SECONDS:
        _trigger_bg_onchain_wallet_sync()
    portfolio.get_or_create_paper_wallet(db)
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    items = list(db.execute(select(Wallet).order_by(Wallet.id.asc())).scalars().all())
    return {
        "usd_idr": usd_idr,
        "wallets": [_wallet_to_dict(w, usd_idr) for w in items],
        "gates": ["main", "trading", "reserve"],
        "treasury": treasury.get_treasury_summary(db),
        "live_engine": live_engine.get_live_engine_status(db, skip_rpc=True),
    }


def sync_wallet_onchain(db: Session, wallet_id: int, apply_onchain_balance: bool = False) -> dict:
    from app.services import live_engine

    w = get_wallet(db, wallet_id)
    if not w:
        raise ValueError("WALLET_NOT_FOUND")
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    rpc_res = live_engine.query_onchain_wallet_balance(w.address, w.chain)
    if (
        apply_onchain_balance
        and rpc_res.get("onchain_balance") is not None
        and not (w.address or "").startswith("11111111111111111111111111111111")
        and not (w.address or "").startswith("SIMULATION")
    ):
        w.balance = float(rpc_res["onchain_balance"])
        w.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(w)
    return {
        "wallet": _wallet_to_dict(w, usd_idr),
        "rpc_check": rpc_res,
    }


def create_wallet(db: Session, data: dict) -> Wallet:
    w = Wallet(
        name=data["name"],
        address=data.get("address", ""),
        chain=data.get("chain", "Solana"),
        balance=float(data.get("balance", 0.0)),
        token=data.get("token", "USDT"),
        gate=data.get("gate", "main"),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def get_wallet(db: Session, wallet_id: int) -> Wallet | None:
    return db.execute(select(Wallet).where(Wallet.id == wallet_id)).scalar_one_or_none()


def update_wallet(db: Session, wallet_id: int, data: dict) -> Wallet:
    w = get_wallet(db, wallet_id)
    if not w:
        raise ValueError("WALLET_NOT_FOUND")
    for f in ("name", "address", "chain", "balance", "token", "gate"):
        if f in data and data[f] is not None:
            setattr(w, f, data[f])
    w.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(w)
    return w


def delete_wallet(db: Session, wallet_id: int) -> bool:
    w = get_wallet(db, wallet_id)
    if not w:
        return False
    db.delete(w)
    db.commit()
    return True

