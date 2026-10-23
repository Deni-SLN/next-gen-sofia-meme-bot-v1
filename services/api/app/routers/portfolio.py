import math
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import portfolio, market

router = APIRouter(dependencies=[Depends(get_current_user)])


class AddHoldingRequest(BaseModel):
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float | None = None
    mode: str = "PAPER"


class SellHoldingRequest(BaseModel):
    symbol: str
    sell_pct: float = 100.0
    mode: str | None = None


class SellAllRequest(BaseModel):
    mode: str | None = None


@router.get("/overview")
def overview(mode: str | None = None, skip_rpc: bool | None = None, db: Session = Depends(get_db)):
    return portfolio.get_overview(db, mode=mode, skip_rpc=skip_rpc)


@router.post("/holdings", status_code=201)
def create_holding(body: AddHoldingRequest, db: Session = Depends(get_db)):
    h = portfolio.add_holding(
        db,
        body.symbol,
        body.quantity,
        body.avg_entry_price,
        body.current_price,
        mode=body.mode,
    )
    return {
        "id": h.id,
        "symbol": h.symbol,
        "mode": h.mode,
        "quantity": h.quantity,
        "avg_entry_price": h.avg_entry_price,
        "current_price": h.current_price,
    }


@router.post("/sell")
def sell_position(body: SellHoldingRequest, db: Session = Depends(get_db)):
    try:
        return portfolio.sell_holding(db, body.symbol, body.sell_pct, mode=body.mode)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SELL_FAILED", "message": str(e)}},
        )


@router.post("/sell-all")
def panic_sell_all(body: SellAllRequest = SellAllRequest(), db: Session = Depends(get_db)):
    try:
        return portfolio.sell_all_holdings(db, mode=body.mode)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SELL_ALL_FAILED", "message": str(e)}},
        )


class ResetPaperRequest(BaseModel):
    initial_capital_usd: float | None = None
    initial_capital_idr: float | None = None


@router.post("/reset-paper")
def reset_paper(body: ResetPaperRequest = ResetPaperRequest(), db: Session = Depends(get_db)):
    return portfolio.reset_paper_account(
        db,
        initial_capital_usd=body.initial_capital_usd,
        initial_capital_idr=body.initial_capital_idr,
    )


class PaperCapitalRequest(BaseModel):
    initial_capital_idr: float | None = None
    initial_capital_usd: float | None = None
    amount_idr: float | None = None
    amount_usd: float | None = None


@router.get("/paper-capital")
def get_paper_capital(db: Session = Depends(get_db)):
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    cap_idr = portfolio.get_paper_initial_capital_idr()
    return {
        "paper_initial_capital_idr": cap_idr,
        "paper_initial_capital_usd": round(cap_idr / usd_idr, 4),
        "usd_idr": usd_idr,
    }


@router.put("/paper-capital")
def set_paper_capital(body: PaperCapitalRequest, db: Session = Depends(get_db)):
    from app.services import bot as bot_svc
    bot_stat = bot_svc.get_bot_status(db)
    if getattr(bot_stat, "status", "") == "running":
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "MODE_TERKUNCI", "message": "Bot sedang berjalan. Matikan bot terlebih dahulu untuk mengubah modal paper."}},
        )
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    cap_idr = body.initial_capital_idr if body.initial_capital_idr is not None else body.amount_idr
    usd_input = body.initial_capital_usd if body.initial_capital_usd is not None else body.amount_usd
    if cap_idr is None and usd_input is not None:
        try:
            usd_val = float(usd_input)
            if math.isnan(usd_val) or math.isinf(usd_val) or usd_val <= 0:
                raise ValueError()
            cap_idr = round(usd_val * usd_idr, 0)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "NOMINAL_TIDAK_VALID", "message": "Nominal modal awal USD tidak valid."}},
            )

    if cap_idr is None:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "NOMINAL_TIDAK_VALID", "message": "Nominal modal awal harus diisi."}},
        )

    try:
        val = float(cap_idr)
        if math.isnan(val) or math.isinf(val) or val <= 0:
            raise ValueError()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "NOMINAL_TIDAK_VALID", "message": "Nominal modal awal harus berupa angka positif."}},
        )

    portfolio.set_paper_initial_capital_idr(val)
    overview_data = portfolio.reset_paper_account(db, initial_capital_idr=val)
    return {
        "message": f"Modal awal paper berhasil diubah menjadi Rp {val:,.0f}",
        "paper_initial_capital_idr": val,
        "paper_initial_capital_usd": round(val / usd_idr, 4),
        "overview": overview_data,
    }
