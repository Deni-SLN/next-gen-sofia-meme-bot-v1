from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import gold

router = APIRouter()


class CreateGoldHoldingRequest(BaseModel):
    weight_grams: float = Field(..., gt=0, description="Berat emas dalam gram (misal: 1, 5, 10)")
    buy_price_per_gram_idr: Optional[float] = Field(None, ge=0, description="Harga beli per gram dalam Rupiah")
    total_cost_idr: Optional[float] = Field(None, ge=0, description="Total modal pembelian dalam Rupiah")
    brand: str = Field(default="Antam", description="Antam, Hartadinata, UBS, Galeri24, atau Digital")
    label: Optional[str] = Field(default="", description="Nama/catatan kepingan emas")
    purchased_at: Optional[str] = Field(default="", description="Tanggal pembelian YYYY-MM-DD")
    notes: Optional[str] = Field(default="", description="Catatan tambahan")


class UpdateGoldHoldingRequest(BaseModel):
    weight_grams: Optional[float] = Field(None, gt=0)
    buy_price_per_gram_idr: Optional[float] = Field(None, ge=0)
    total_cost_idr: Optional[float] = Field(None, ge=0)
    brand: Optional[str] = Field(None)
    label: Optional[str] = Field(None)
    purchased_at: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


class SimulateGoldSellRequest(BaseModel):
    weight_grams: float = Field(..., gt=0)
    total_cost_idr: float = Field(default=0, ge=0)
    retail_buy_price_per_gram_idr: Optional[float] = Field(default=None, ge=0)
    spread_pct: float = Field(default=9.0, ge=0, le=50)
    tax_pct: Optional[float] = Field(default=None, ge=0, le=25)
    has_npwp: bool = Field(default=True)
    include_stamp_duty: bool = Field(default=True)


@router.get("")
@router.get("/")
def get_gold_overview(
    refresh: bool = Query(default=False, description="Force refresh live XAU/USD & IDR gold prices"),
    db: Session = Depends(get_db),
):
    return gold.get_gold_dashboard(db=db, force_refresh=refresh)


@router.post("/holdings")
def create_gold_holding_endpoint(
    payload: CreateGoldHoldingRequest,
    db: Session = Depends(get_db),
):
    gold.add_gold_holding(
        db=db,
        weight_grams=payload.weight_grams,
        buy_price_per_gram_idr=payload.buy_price_per_gram_idr,
        total_cost_idr=payload.total_cost_idr,
        brand=payload.brand,
        label=payload.label or "",
        purchased_at=payload.purchased_at or "",
        notes=payload.notes or "",
    )
    return gold.get_gold_dashboard(db=db, force_refresh=False)


@router.put("/holdings/{holding_id}")
def update_gold_holding_endpoint(
    holding_id: int,
    payload: UpdateGoldHoldingRequest,
    db: Session = Depends(get_db),
):
    updated = gold.update_gold_holding(
        db=db,
        holding_id=holding_id,
        weight_grams=payload.weight_grams,
        buy_price_per_gram_idr=payload.buy_price_per_gram_idr,
        total_cost_idr=payload.total_cost_idr,
        brand=payload.brand,
        label=payload.label,
        purchased_at=payload.purchased_at,
        notes=payload.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Data kepemilikan emas tidak ditemukan")
    return gold.get_gold_dashboard(db=db, force_refresh=False)


@router.delete("/holdings/{holding_id}")
def delete_gold_holding_endpoint(
    holding_id: int,
    db: Session = Depends(get_db),
):
    deleted = gold.delete_gold_holding(db=db, holding_id=holding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data kepemilikan emas tidak ditemukan")
    return gold.get_gold_dashboard(db=db, force_refresh=False)


@router.post("/simulate-sell")
def simulate_gold_sell_endpoint(
    payload: SimulateGoldSellRequest,
):
    market_data = gold.fetch_live_gold_market(force_refresh=False)
    retail_price = (
        payload.retail_buy_price_per_gram_idr
        if payload.retail_buy_price_per_gram_idr and payload.retail_buy_price_per_gram_idr > 0
        else float(market_data["antam"]["buy_price_idr"])
    )
    return gold.simulate_sell_now(
        weight_grams=payload.weight_grams,
        total_cost_idr=payload.total_cost_idr,
        retail_buy_price_per_gram_idr=retail_price,
        spread_pct=payload.spread_pct,
        tax_pct=payload.tax_pct,
        has_npwp=payload.has_npwp,
        include_stamp_duty=payload.include_stamp_duty,
    )
