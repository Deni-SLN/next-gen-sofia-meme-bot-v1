from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import stocks

router = APIRouter()


class RiskCalculatorRequest(BaseModel):
    capital_idr: float = Field(..., description="Modal tersedia dalam Rupiah")
    entry_price: float = Field(..., description="Harga rencana beli (Entry)")
    stop_loss: float = Field(..., description="Harga Stop Loss")
    target_price: float = Field(..., description="Harga Target Profit (TP)")
    max_risk_pct: float = Field(default=2.0, description="Batas risiko maksimum per transaksi (%)")
    lots: Optional[int] = Field(default=None, description="Jumlah lot (1 lot BEI = 100 lembar)")
    buy_fee_pct: float = Field(default=0.15, description="Biaya transaksi beli sekuritas (%)")
    sell_fee_pct: float = Field(default=0.25, description="Biaya transaksi jual sekuritas (%)")
    slippage_pct: float = Field(default=0.20, description="Estimasi slippage eksekusi (%)")
    existing_portfolio_value_idr: float = Field(default=0.0, description="Nilai portofolio saham saat ini (Rp)")
    is_idx: bool = Field(default=True)


class StockPortfolioPositionRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    lots: int = Field(..., gt=0)
    avg_buy_price: float = Field(..., gt=0)
    notes: Optional[str] = Field(default="")


class StockWatchlistRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    target_entry_price: Optional[float] = Field(default=None)
    target_tp_price: Optional[float] = Field(default=None)
    stop_loss_price: Optional[float] = Field(default=None)
    notes: Optional[str] = Field(default="")


class StockSignalJournalRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    timeframe: str = Field(default="1d")
    notes: Optional[str] = Field(default="")


@router.get("/analyze")
@router.get("")
@router.get("/")
def get_stock_analysis(
    q: str = Query("BBRI", description="Kode saham BEI / IDX (contoh: BBRI, BBCA, BMRI, TLKM, ANTM, ADRO, IHSG)"),
    timeframe: str = Query("1d", description="Time frame Trading Plan: 15m, 1h, 1d, 1w, 1mo, 1y"),
    refresh: bool = Query(False, description="Paksa muat ulang data terbaru"),
):
    try:
        return stocks.analyze_stock(query=q, timeframe=timeframe, force_refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal menganalisis saham '{q}': {exc}")


@router.post("/risk-calculator")
def calculate_stock_risk_endpoint(payload: RiskCalculatorRequest):
    try:
        return stocks.calculate_idx_position_risk(
            capital_idr=payload.capital_idr,
            entry_price=payload.entry_price,
            stop_loss=payload.stop_loss,
            target_price=payload.target_price,
            max_risk_pct=payload.max_risk_pct,
            lots=payload.lots,
            buy_fee_pct=payload.buy_fee_pct,
            sell_fee_pct=payload.sell_fee_pct,
            slippage_pct=payload.slippage_pct,
            existing_portfolio_value_idr=payload.existing_portfolio_value_idr,
            is_idx=payload.is_idx,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/portfolio")
def get_stock_portfolio_endpoint(db: Session = Depends(get_db)):
    return stocks.get_stock_portfolio_and_watchlist(db)


@router.post("/portfolio")
def upsert_stock_portfolio_endpoint(payload: StockPortfolioPositionRequest, db: Session = Depends(get_db)):
    try:
        return stocks.upsert_stock_portfolio_position(
            db=db,
            code=payload.code,
            lots=payload.lots,
            avg_buy_price=payload.avg_buy_price,
            notes=payload.notes or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/portfolio/{position_id}")
def delete_stock_portfolio_endpoint(position_id: int, db: Session = Depends(get_db)):
    return stocks.delete_stock_portfolio_position(db=db, position_id=position_id)


@router.post("/watchlist")
def upsert_stock_watchlist_endpoint(payload: StockWatchlistRequest, db: Session = Depends(get_db)):
    return stocks.upsert_stock_watchlist_item(
        db=db,
        code=payload.code,
        target_entry_price=payload.target_entry_price,
        target_tp_price=payload.target_tp_price,
        stop_loss_price=payload.stop_loss_price,
        notes=payload.notes or "",
    )


@router.delete("/watchlist/{item_id}")
def delete_stock_watchlist_endpoint(item_id: int, db: Session = Depends(get_db)):
    return stocks.delete_stock_watchlist_item(db=db, item_id=item_id)


@router.post("/signal-journal")
def record_stock_signal_journal_endpoint(payload: StockSignalJournalRequest, db: Session = Depends(get_db)):
    try:
        return stocks.record_stock_signal_journal(
            db=db,
            code=payload.code,
            timeframe=payload.timeframe,
            notes=payload.notes or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
