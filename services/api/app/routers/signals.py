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
    return {"signals": [_row_to_dict(s) for s in items], "total": total}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_new_signal(
    body: SignalCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_user),
):
    sig = signals.create_signal(db, body.model_dump())
    return _row_to_dict(sig)
