from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import performance

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    return performance.get_summary(db)


@router.get("/daily-calendar")
def get_daily_calendar(
    mode: str = "ALL",
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    return performance.get_daily_calendar(db, mode=mode, year=year, month=month)
