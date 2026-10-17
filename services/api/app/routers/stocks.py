from fastapi import APIRouter, HTTPException, Query
from app.services import stocks

router = APIRouter()


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
