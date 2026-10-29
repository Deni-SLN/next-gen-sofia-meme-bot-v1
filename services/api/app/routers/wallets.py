from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import wallets, treasury, portfolio

router = APIRouter(dependencies=[Depends(get_current_user)])


def _row_to_dict(obj) -> dict:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat() if v else None
    return d


class WalletCreateRequest(BaseModel):
    name: str
    address: str = ""
    chain: str = "Ethereum"
    balance: float = 0.0
    token: str = "USDT"
    gate: str = "main"


class WalletUpdateRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    chain: str | None = None
    balance: float | None = None
    token: str | None = None
    gate: str | None = None


class GasTopUpRequest(BaseModel):
    amount_idr: float = 5000.0


class SettlementRequest(BaseModel):
    trigger: str = "manual_check_0500_wib"
    simulate_net_profit_idr: float | None = None


@router.get("")
@router.get("/")
def list_all_wallets(db: Session = Depends(get_db)):
    return wallets.list_wallets(db)


@router.get("/treasury/summary")
def get_treasury_info(db: Session = Depends(get_db)):
    return treasury.get_treasury_summary(db)


@router.post("/treasury/topup-gas")
def topup_gas_reserve(body: GasTopUpRequest, db: Session = Depends(get_db)):
    paper_wallet, usd_idr = portfolio.get_or_create_paper_wallet(db)
    res = treasury.ensure_gas_reserve(
        db,
        paper_wallet=paper_wallet,
        usd_idr=usd_idr,
        force_topup_idr=body.amount_idr,
    )
    return {
        "topup": res,
        "treasury": treasury.get_treasury_summary(db),
    }


@router.post("/treasury/settle")
def trigger_settlement(body: SettlementRequest, db: Session = Depends(get_db)):
    return treasury.run_daily_settlement(
        db,
        trigger=body.trigger,
        simulate_net_profit_idr=body.simulate_net_profit_idr,
    )


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_wallet(body: WalletCreateRequest, db: Session = Depends(get_db)):
    w = wallets.create_wallet(db, body.model_dump())
    return _row_to_dict(w)


class SyncOnchainRequest(BaseModel):
    apply_onchain_balance: bool = False


class PrimarySolanaWalletRequest(BaseModel):
    address: str
    name: str | None = "Dompet Utama Solana (Pengaturan Sistem)"


@router.post("/primary-solana")
def set_primary_solana_wallet(body: PrimarySolanaWalletRequest, db: Session = Depends(get_db)):
    w_dict = wallets.set_primary_solana_wallet(db, address=body.address, name=body.name)
    return {"status": "ok", "wallet": w_dict}


@router.get("/live-status")
def get_live_status(db: Session = Depends(get_db)):
    from app.services import live_engine
    return live_engine.get_live_engine_status(db, skip_rpc=True)


@router.post("/{wallet_id}/sync-onchain")
def sync_wallet_rpc(wallet_id: int, body: SyncOnchainRequest = SyncOnchainRequest(), db: Session = Depends(get_db)):
    try:
        return wallets.sync_wallet_onchain(db, wallet_id, apply_onchain_balance=body.apply_onchain_balance)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": {"code": str(e), "message": "Wallet not found"}})


@router.get("/{wallet_id}")
def get_wallet(wallet_id: int, db: Session = Depends(get_db)):
    w = wallets.get_wallet(db, wallet_id)
    if not w:
        return JSONResponse(status_code=404, content={"error": {"code": "WALLET_NOT_FOUND", "message": "Wallet not found"}})
    return _row_to_dict(w)


@router.put("/{wallet_id}")
def update_wallet(wallet_id: int, body: WalletUpdateRequest, db: Session = Depends(get_db)):
    try:
        w = wallets.update_wallet(db, wallet_id, body.model_dump(exclude_unset=True))
        return _row_to_dict(w)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": {"code": str(e), "message": "Wallet not found"}})


@router.delete("/{wallet_id}")
def delete_wallet(wallet_id: int, db: Session = Depends(get_db)):
    ok = wallets.delete_wallet(db, wallet_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": {"code": "WALLET_NOT_FOUND", "message": "Wallet not found"}})
    return {"deleted": True}

