from typing import Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.services import auto_entry

router = APIRouter()


class AutoEntryConfigRequest(BaseModel):
    entry_amount_idr: Optional[float] = Field(None, ge=1000.0, description="Nominal uang per entry dalam Rupiah")
    entry_amount_usd: Optional[float] = Field(None, ge=0.1, description="Nominal uang per entry dalam USD")
    max_entries: Optional[int] = Field(None, ge=1, le=50, description="Batas maksimal posisi entry")
    slippage_pct: Optional[float] = Field(None, ge=0.1, le=25.0, description="Toleransi slippage (%)")
    min_safety_score: Optional[int] = Field(None, ge=0, le=100, description="Batas minimal skor keamanan")
    mode: Optional[str] = Field(None, description="PAPER | LIVE")
    target_source: Optional[str] = Field(None, description="ALL_RADAR | NEW_CREATIONS | FINAL_STRETCH | MIGRATED")


class StartAutoEntryRequest(BaseModel):
    entry_amount_idr: Optional[float] = Field(None, ge=1000.0)
    entry_amount_usd: Optional[float] = Field(None, ge=0.1)
    max_entries: Optional[int] = Field(None, ge=1, le=50)
    slippage_pct: Optional[float] = Field(None, ge=0.1, le=25.0)
    min_safety_score: Optional[int] = Field(None, ge=0, le=100)
    mode: Optional[str] = Field(None)
    target_source: Optional[str] = Field(None)


@router.get("/status")
def get_auto_entry_status():
    """Retrieve current auto entry configuration, status, counter, and execution history."""
    return auto_entry.get_auto_entry_state()


@router.post("/start")
def start_auto_entry_bot(
    body: Optional[StartAutoEntryRequest] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Start autonomous auto entry scanning and order execution."""
    params = body.model_dump(exclude_none=True) if body else None
    return auto_entry.start_auto_entry(params, db)


@router.post("/stop")
def stop_auto_entry_bot(user=Depends(get_current_user)):
    """Stop autonomous auto entry bot."""
    return auto_entry.stop_auto_entry()


@router.put("/config")
def update_auto_entry_parameters(
    body: AutoEntryConfigRequest,
    user=Depends(get_current_user),
):
    """Update auto entry parameters (amount, max entries, slippage, etc.)."""
    return auto_entry.update_auto_entry_config(body.model_dump(exclude_none=True))


@router.post("/reset-counter")
def reset_auto_entry_counter(user=Depends(get_current_user)):
    """Reset filled entries counter and session history back to 0."""
    return auto_entry.reset_auto_entry_counter()


@router.post("/trigger-scan")
def trigger_manual_scan_tick(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Trigger a single manual scan & entry tick immediately."""
    return auto_entry.trigger_manual_scan_tick(db)
