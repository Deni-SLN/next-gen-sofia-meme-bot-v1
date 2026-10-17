from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import crypto_analysis

router = APIRouter()


class CryptoRiskCalculatorRequest(BaseModel):
    capital_idr: float = Field(..., description="Total modal portofolio kripto dalam Rupiah")
    entry_price_usd: float = Field(..., description="Harga rencana beli (Entry) dalam USD")
    stop_loss_usd: float = Field(..., description="Harga Stop Loss dalam USD")
    target_price_usd: float = Field(..., description="Harga Target Profit (TP) dalam USD")
    max_risk_pct: float = Field(default=2.0, description="Batas risiko maksimum per transaksi (%)")
    investment_idr: Optional[float] = Field(default=None, description="Nominal alokasi beli kripto dalam Rupiah")
    exchange_fee_pct: float = Field(default=0.10, description="Biaya transaksi bursa kripto per sisi (%)")
    tax_pct: float = Field(default=0.21, description="Pajak kripto Bappebti/OJK PPh+PPN (%)")


@router.get("/analyze")
@router.get("")
@router.get("/")
def get_crypto_analysis_endpoint(
    q: str = Query("BTC", description="Kode koin/token kripto (contoh: BTC, ETH, SOL, BNB, XRP, DOGE, SUI, ADA, AVAX, LINK, TON, PEPE, BONK)"),
    timeframe: str = Query("1d", description="Timeframe Trading Plan: 15m, 1h, 4h, 1d, 1w, 1mo"),
    refresh: bool = Query(False, description="Paksa muat ulang data terbaru"),
):
    try:
        return crypto_analysis.analyze_crypto(query=q, timeframe=timeframe, force_refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal menganalisis kripto '{q}': {exc}")


@router.post("/risk-calculator")
def calculate_crypto_risk_endpoint(payload: CryptoRiskCalculatorRequest):
    try:
        return crypto_analysis.calculate_crypto_position_risk(
            capital_idr=payload.capital_idr,
            entry_price_usd=payload.entry_price_usd,
            stop_loss_usd=payload.stop_loss_usd,
            target_price_usd=payload.target_price_usd,
            max_risk_pct=payload.max_risk_pct,
            investment_idr=payload.investment_idr,
            exchange_fee_pct=payload.exchange_fee_pct,
            tax_pct=payload.tax_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
