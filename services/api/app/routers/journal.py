from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import journal

router = APIRouter(dependencies=[Depends(get_current_user)])


class TradeRecordRequest(BaseModel):
    symbol: str
    side: str = "sell"
    quantity: float
    price: float
    total: float
    pnl: float = 0.0
    slippage_pct: float = 1.0
    dex_fee_usd: float = 0.0
    gas_fee_usd: float = 0.05
    chain: str = "Solana"
    status: str = "closed"
    tx_hash: str = ""
    notes: str = ""


@router.get("")
@router.get("/")
def get_live_journal(
    q: str | None = Query(None, description="Filter by symbol or chain"),
    outcome: str | None = Query(None, description="Filter by WIN, LOSS, OPEN"),
    limit: int = Query(10, ge=1, le=100, description="Max trades to return for display (default 10)"),
    db: Session = Depends(get_db),
):
    """Retrieve Live Trading Journal summary with 4 Cards and 10 latest transactions stored in Neonbase."""
    return journal.get_journal_summary(db, token_filter=q, outcome_filter=outcome, limit=limit)


@router.get("/export-excel")
@router.get("/export-csv")
def export_journal_excel(db: Session = Depends(get_db)):
    """Export ALL live trading journal transactions from Neonbase into an Excel-ready CSV file."""
    csv_content = journal.export_journal_csv(db)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Jurnal_Trading_Live_Neonbase_{now_str}.csv"
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.post("/trades")
def add_journal_trade(body: TradeRecordRequest, db: Session = Depends(get_db)):
    """Record a live bot trade or verified transaction directly into Neonbase."""
    trade = journal.record_live_trade(db, body.model_dump())
    return {
        "status": "success",
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "message": f"Transaksi live bot {trade.symbol} berhasil disimpan di Neonbase.",
    }


@router.delete("/trades/{trade_id}")
def delete_journal_trade(trade_id: int, db: Session = Depends(get_db)):
    """Delete a trade record from the live journal."""
    success = journal.delete_live_trade(db, trade_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trade record tidak ditemukan.")
    return {"status": "deleted", "trade_id": trade_id}
