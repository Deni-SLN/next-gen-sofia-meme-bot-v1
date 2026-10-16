from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import memecoins, market

router = APIRouter(dependencies=[Depends(get_current_user)])


class SnipeRequest(BaseModel):
    symbol: str
    amount_usd: float = 1.5
    amount_idr: float | None = None
    price: float = 0.0001
    slippage_pct: float = 15.0
    priority_fee_sol: float = 0.005
    anti_mev: bool = True
    force_unsafe: bool = False
    mode: str = "PAPER"


class CopyToggleRequest(BaseModel):
    enabled: bool
    max_copy_usd: float | None = None


@router.get("/fx")
def get_fx():
    return market.get_fx_rate()


@router.get("/pulse")
def get_pulse():
    return memecoins.get_pulse_feed()


@router.get("/rugcheck")
def rug_check(q: str = Query(..., description="Token symbol or contract address")):
    return memecoins.analyze_rug_check(q)


@router.post("/snipe")
def snipe_token(body: SnipeRequest, db: Session = Depends(get_db)):
    try:
        return memecoins.execute_snipe(db, body.model_dump())
    except ValueError as e:
        msg = str(e)
        code = "RUG_SHIELD_BLOCKED"
        if "LIVE_NOT_CONFIGURED" in msg:
            code = "LIVE_NOT_CONFIGURED"
        elif "SALDO_PAPER_TIDAK_CUKUP" in msg:
            code = "INSUFFICIENT_PAPER_BALANCE"
        return JSONResponse(
            status_code=400,
            content={"error": {"code": code, "message": msg}},
        )


@router.get("/smart-money")
def get_smart_money():
    return memecoins.list_smart_money()


@router.post("/smart-money/{wallet_id}/toggle")
def toggle_copy(wallet_id: int, body: CopyToggleRequest):
    try:
        return memecoins.toggle_copy_wallet(wallet_id, body.enabled, body.max_copy_usd)
    except ValueError as e:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": str(e), "message": "Smart money wallet not found"}},
        )
