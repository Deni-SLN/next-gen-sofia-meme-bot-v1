"""
macro.py — FastAPI Router for Macroeconomic & Quantitative Factor Intelligence.
Integrates directly with Fincept Terminal FastMCP running in Proxmox CT 106.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.services.fincept_client import (
    get_macro_indicators,
    get_market_data,
    run_factor_backtest,
    search_symbols,
)

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g. AAPL, BTC-USD, BBCA.JK)")
    factor_expr: str = Field(..., description="Factor expression (e.g. 'close.rolling(20).mean() / close - 1.0')")
    period: str = Field(default="1y", description="Backtest lookback period: '1mo', '3mo', '6mo', '1y', '2y'")


@router.get("/indicators", summary="Indikator Makroekonomi Terkini (Fincept Terminal CT 106)")
async def get_macro(refresh: bool = Query(default=False, description="Paksa refresh cache")):
    """
    Mengambil data makroekonomi institusional:
    - VIX (CBOE Volatility Index & Regime Sentimen Risiko)
    - US 10-Year Treasury Yield (^TNX)
    - US 2-Year Treasury Yield (^IRX) & Spread Kurva Imbal Hasil
    - US Dollar Index DXY (DX-Y.NYB)
    - Minyak Mentah WTI (CL=F)
    """
    res = get_macro_indicators(force_refresh=refresh)
    if "error" in res and not res.get("indicators"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res


@router.get("/market-data", summary="Data Bar Historis Multi-Asset (Fincept Terminal)")
async def get_bars(
    symbol: str = Query(..., description="Ticker simbol (misal: BTC-USD, AAPL)"),
    period: str = Query(default="5d", description="Lookback: 1d, 5d, 1mo, 3mo, 1y"),
    interval: str = Query(default="1d", description="Interval: 1m, 5m, 15m, 1h, 1d"),
):
    res = get_market_data(symbol=symbol, period=period, interval=interval)
    if "error" in res and not res.get("bars"):
        raise HTTPException(status_code=502, detail=res.get("error"))
    return res


@router.post("/backtest", summary="Quantitative Factor Backtest Engine (Fincept Terminal)")
async def post_backtest(req: BacktestRequest):
    res = run_factor_backtest(symbol=req.symbol, factor_expr=req.factor_expr, period=req.period)
    if "error" in res and not res.get("ic"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/search", summary="Pencarian Simbol Multi-Asset Universal")
async def search(query: str = Query(..., description="Nama atau ticker simbol"), limit: int = 10):
    return search_symbols(query=query, limit=limit)
