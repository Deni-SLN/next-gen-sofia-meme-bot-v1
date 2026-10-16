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


class SniperConfigUpdateRequest(BaseModel):
    relay_mode: str | None = None
    slippage_pct: float | None = None
    priority_fee_sol: float | None = None
    jito_bribe_sol: float | None = None
    anti_mev: bool | None = None
    buy_amount_idr: float | None = None
    min_safety_score: int | None = None
    min_liquidity_usd: float | None = None
    min_bonding_curve_pct: float | None = None
    max_bonding_curve_pct: float | None = None
    max_dev_holding_pct: float | None = None
    max_top10_holding_pct: float | None = None
    require_mint_revoked: bool | None = None
    require_freeze_revoked: bool | None = None
    require_lp_burned: bool | None = None
    auto_tp_pct: float | None = None
    auto_tp_sell_pct: float | None = None
    auto_sl_pct: float | None = None
    trailing_stop_enabled: bool | None = None
    trailing_stop_pct: float | None = None
    time_stop_minutes: int | None = None
    multi_wallet_rotation: bool | None = None


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    state = bot.get_bot_status(db)
    data = _row_to_dict(state)
    data["sniper_config"] = bot.get_sniper_config()
    return data


@router.get("/config")
def get_config():
    return bot.get_sniper_config()


@router.put("/config")
def update_config(body: SniperConfigUpdateRequest):
    return bot.update_sniper_config(body.model_dump(exclude_unset=True))


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
        data = _row_to_dict(state)
        data["sniper_config"] = bot.get_sniper_config()
        return data
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
        data = _row_to_dict(state)
        data["sniper_config"] = bot.get_sniper_config()
        return data
    except ValueError as e:
        code = str(e)
        return JSONResponse(
            status_code=409,
            content={"error": {"code": code, "message": f"Cannot stop bot: {code}"}},
        )

