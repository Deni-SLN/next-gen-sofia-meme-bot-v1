from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import portfolio

router = APIRouter(dependencies=[Depends(get_current_user)])


class AddHoldingRequest(BaseModel):
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float | None = None


class SellHoldingRequest(BaseModel):
    symbol: str
    sell_pct: float = 100.0
    mode: str | None = None


class SellAllRequest(BaseModel):
    mode: str | None = None


@router.get("/overview")
def overview(mode: str | None = None, db: Session = Depends(get_db)):
    return portfolio.get_overview(db, mode=mode)


@router.post("/holdings", status_code=201)
def create_holding(body: AddHoldingRequest, db: Session = Depends(get_db)):
    h = portfolio.add_holding(db, body.symbol, body.quantity, body.avg_entry_price, body.current_price)
    return {
        "id": h.id,
        "symbol": h.symbol,
        "quantity": h.quantity,
        "avg_entry_price": h.avg_entry_price,
        "current_price": h.current_price,
    }


@router.post("/sell")
def sell_position(body: SellHoldingRequest, db: Session = Depends(get_db)):
    try:
        return portfolio.sell_holding(db, body.symbol, body.sell_pct, mode=body.mode)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SELL_FAILED", "message": str(e)}},
        )


@router.post("/sell-all")
def panic_sell_all(body: SellAllRequest = SellAllRequest(), db: Session = Depends(get_db)):
    try:
        return portfolio.sell_all_holdings(db, mode=body.mode)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SELL_ALL_FAILED", "message": str(e)}},
        )


@router.post("/reset-paper")
def reset_paper(db: Session = Depends(get_db)):
    return portfolio.reset_paper_account(db)

