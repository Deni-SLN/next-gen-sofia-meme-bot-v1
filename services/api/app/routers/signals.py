from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import signals

router = APIRouter(dependencies=[Depends(get_current_user)])


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


@router.get("")
@router.get("/")
def list_all_signals(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = signals.list_signals(db, status=status, limit=limit, offset=offset)
    return {"signals": [_row_to_dict(s) for s in items], "total": total}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_new_signal(body: SignalCreateRequest, db: Session = Depends(get_db)):
    sig = signals.create_signal(db, body.model_dump())
    return _row_to_dict(sig)
