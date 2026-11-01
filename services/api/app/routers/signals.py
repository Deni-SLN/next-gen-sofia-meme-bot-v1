from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import security_scheme, verify_token
from app.db.session import get_db
from app.services import signals

router = APIRouter()


def _get_optional_user(credentials=Depends(security_scheme)) -> Optional[dict]:
    if not credentials or not credentials.credentials:
        return None
    try:
        return verify_token(credentials.credentials)
    except Exception:
        return None


def _require_user(credentials=Depends(security_scheme)) -> dict:
    if not credentials or not credentials.credentials:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)


def _row_to_dict(obj) -> dict:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat() if v else None
    return d


class SignalCreateRequest(BaseModel):
    symbol: str
    direction: str
    confidence: float = 0.8
    source: str = "AI_ENGINE"
    timeframe: str = "1h"
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


@router.get("/insights")
def get_signal_insights(
    refresh: bool = Query(default=False, description="Force fresh analysis calculation"),
    user: Optional[dict] = Depends(_get_optional_user),
):
    """
    Returns top 5 curated Stock Insights (IDX) and top 5 curated Crypto Insights (Global)
    complete with live prices, trading plans, safety scores, technical indicators, and catalysts.
    """
    return signals.get_all_insights(force_refresh=refresh)


@router.get("/stock-insights")
def get_stock_insights(
    refresh: bool = Query(default=False, description="Force fresh stock analysis"),
    user: Optional[dict] = Depends(_get_optional_user),
):
    """
    Returns 5 top attractive IDX stocks to watch (e.g. BBCA, BBRI, TLKM, ASII, ANTM).
    """
    return signals.get_curated_stock_insights(force_refresh=refresh)


@router.get("/crypto-insights")
def get_crypto_insights(
    refresh: bool = Query(default=False, description="Force fresh crypto analysis"),
    user: Optional[dict] = Depends(_get_optional_user),
):
    """
    Returns 5 top attractive Global Crypto assets to watch (e.g. BTC, ETH, SOL, SUI, AVAX).
    """
    return signals.get_curated_crypto_insights(force_refresh=refresh)


@router.get("")
@router.get("/")
def list_all_signals(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(_get_optional_user),
):
    items, total = signals.list_signals(db, status=status, limit=limit, offset=offset)
    rows = [_row_to_dict(s) for s in items]
    if len(rows) < 5:
        try:
            insights = signals.get_all_insights(force_refresh=False)
            synth_id = 9000
            for c in (insights.get("crypto") or [])[:5]:
                synth_id += 1
                rows.append({
                    "id": synth_id,
                    "symbol": c["symbol"],
                    "direction": "LONG / BUY" if float(c.get("change_24h_pct") or 0) >= -2.0 else "ACCUMULATE DIP",
                    "confidence": round(min(0.96, max(0.75, float(c.get("safety_score", 88)) / 100.0)), 2),
                    "timeframe": "1D / 4H",
                    "source": f"SOFIA QUANT ENGINE ({c.get('technical_summary', 'RSI & Trend')})",
                    "entry_price": c.get("current_price_usd"),
                    "take_profit": c.get("tp_1_usd"),
                    "stop_loss": c.get("stop_loss_usd"),
                    "status": "ACTIVE",
                })
            for st in (insights.get("stocks") or [])[:5]:
                synth_id += 1
                rows.append({
                    "id": synth_id,
                    "symbol": f"{st['ticker']}.JK",
                    "direction": "ACCUMULATE",
                    "confidence": round(min(0.97, max(0.78, float(st.get("safety_score", 90)) / 100.0)), 2),
                    "timeframe": "1D (IDX)",
                    "source": f"IDX FUNDAMENTAL & TECH ({st.get('technical_summary', 'Support')})",
                    "entry_price": st.get("current_price"),
                    "take_profit": st.get("tp_1"),
                    "stop_loss": st.get("stop_loss"),
                    "status": "ACTIVE",
                })
            total = len(rows)
        except Exception:
            pass
    return {"signals": rows[:limit], "total": total}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_new_signal(
    body: SignalCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_user),
):
    sig = signals.create_signal(db, body.model_dump())
    return _row_to_dict(sig)
