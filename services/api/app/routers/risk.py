from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import risk

router = APIRouter(dependencies=[Depends(get_current_user)])


def _row_to_dict(obj) -> dict:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat() if v else None
    return d


class RiskUpdateRequest(BaseModel):
    max_position_size_pct: float | None = None
    max_daily_loss_pct: float | None = None
    max_drawdown_pct: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_open_positions: int | None = None
    allowed_symbols: list[str] | None = None


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = risk.get_risk_config(db)
    return _row_to_dict(cfg)


@router.put("/config")
def update_config(body: RiskUpdateRequest, db: Session = Depends(get_db)):
    cfg = risk.update_risk_config(db, body.model_dump(exclude_unset=True))
    return _row_to_dict(cfg)
