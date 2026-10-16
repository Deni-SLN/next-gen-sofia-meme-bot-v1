from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import RiskConfig


def get_risk_config(db: Session) -> RiskConfig:
    cfg = db.execute(select(RiskConfig).where(RiskConfig.id == 1)).scalar_one_or_none()
    if not cfg:
        cfg = RiskConfig(
            id=1,
            max_position_size_pct=5.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=10.0,
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
            max_open_positions=10,
            allowed_symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            updated_at=datetime.now(timezone.utc),
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def update_risk_config(db: Session, data: dict) -> RiskConfig:
    cfg = get_risk_config(db)
    fields = (
        "max_position_size_pct",
        "max_daily_loss_pct",
        "max_drawdown_pct",
        "stop_loss_pct",
        "take_profit_pct",
        "max_open_positions",
        "allowed_symbols",
    )
    for f in fields:
        if f in data and data[f] is not None:
            setattr(cfg, f, data[f])
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return cfg
