from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Wallet
from app.services import market, portfolio, treasury


def _wallet_to_dict(w: Wallet, usd_idr: float) -> dict:
    # Estimate USD value if token is SOL (~$140) or USD/USDT/USDC
    token_upper = (w.token or "USDT").upper()
    if "SOL" in token_upper and "USD" not in token_upper:
        sol_info = market.get_live_token_info("SOL/USDT")
        sol_price = float(sol_info["price"]) if (sol_info and sol_info.get("price", 0) > 10) else 145.0
        usd_val = w.balance * sol_price
    else:
        usd_val = w.balance

    return {
        "id": w.id,
        "name": w.name,
        "address": w.address,
        "chain": w.chain,
        "balance": round(w.balance, 4),
        "balance_usd": round(usd_val, 2),
        "balance_idr": round(usd_val * usd_idr, 0),
        "token": w.token,
        "gate": w.gate,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def list_wallets(db: Session) -> dict:
    from app.services import live_engine

    portfolio.get_or_create_paper_wallet(db)
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    items = list(db.execute(select(Wallet).order_by(Wallet.id.asc())).scalars().all())
    return {
        "usd_idr": usd_idr,
        "wallets": [_wallet_to_dict(w, usd_idr) for w in items],
        "gates": ["main", "trading", "reserve"],
        "treasury": treasury.get_treasury_summary(db),
        "live_engine": live_engine.get_live_engine_status(db),
    }


def sync_wallet_onchain(db: Session, wallet_id: int, apply_onchain_balance: bool = False) -> dict:
    from app.services import live_engine

    w = get_wallet(db, wallet_id)
    if not w:
        raise ValueError("WALLET_NOT_FOUND")
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    rpc_res = live_engine.query_onchain_wallet_balance(w.address, w.chain)
    if apply_onchain_balance and rpc_res.get("onchain_balance") is not None:
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

