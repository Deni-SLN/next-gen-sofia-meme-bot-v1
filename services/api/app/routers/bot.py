from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import bot

router = APIRouter(dependencies=[Depends(get_current_user)])


def _row_to_dict(obj) -> dict:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat() if v else None
    return d


class StartBotRequest(BaseModel):
    mode: str = "PAPER"


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    state = bot.get_bot_status(db)
    return _row_to_dict(state)


@router.get("/activity")
def get_activity(
    tick: bool = Query(default=True),
    force_trade: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return bot.get_bot_activity(db, tick=tick, force_trade=force_trade)


@router.post("/start")
def start(body: StartBotRequest, db: Session = Depends(get_db)):
    try:
        state = bot.start_bot(db, body.mode)
        return _row_to_dict(state)
    except ValueError as e:
        code = str(e)
        status_code = 400 if code == "LIVE_NOT_CONFIGURED" else 409
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": f"Cannot start bot: {code}"}},
        )


@router.post("/stop")
def stop(db: Session = Depends(get_db)):
    try:
        state = bot.stop_bot(db)
        return _row_to_dict(state)
    except ValueError as e:
        code = str(e)
        return JSONResponse(
            status_code=409,
            content={"error": {"code": code, "message": f"Cannot stop bot: {code}"}},
        )
