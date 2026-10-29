from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from fastapi.responses import JSONResponse
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
    mode: str = "LIVE"
    status: str = "closed"
    tx_hash: str = ""
    notes: str = ""


class SyncWalletRequest(BaseModel):
    wallet_address: str = "8muJ3h4PPLmXhAVpJf8dnp9m17WsSaPNm9dSHcTsMVos"


@router.get("")
@router.get("/")
def get_live_journal(
    q: str | None = Query(None, description="Filter by symbol or chain"),
    outcome: str | None = Query(None, description="Filter by WIN, LOSS, OPEN"),
    mode: str = Query("LIVE", description="PAPER | LIVE | WALLET"),
    wallet_address: str | None = Query(None, description="Solana wallet address from System Settings"),
    limit: int = Query(20, ge=1, le=20, description="Max trades per page (max 20)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    db: Session = Depends(get_db),
):
    """Retrieve Trading Journal summary separated by mode (PAPER | LIVE | WALLET)."""
    return journal.get_journal_summary(
        db,
        token_filter=q,
        outcome_filter=outcome,
        limit=limit,
        page=page,
        mode=mode,
        wallet_address=wallet_address,
    )


@router.post("/sync-wallet")
def sync_wallet_journal(body: SyncWalletRequest, db: Session = Depends(get_db)):
    """Sync on-chain transactions for the user's configured Solana wallet into mode='WALLET'."""
    return journal.sync_solana_wallet_onchain_trades(db, body.wallet_address)


@router.get("/export-excel")
@router.get("/export-csv")
def export_journal_excel(
    mode: str = Query("LIVE", description="PAPER | LIVE | WALLET"),
    db: Session = Depends(get_db),
):
    """Export trading journal transactions for the selected mode (PAPER | LIVE | WALLET) into an Excel-ready CSV file."""
    csv_content = journal.export_journal_csv(db, mode=mode)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Jurnal_Trading_{mode.upper()}_Neonbase_{now_str}.csv"
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
    try:
        trade = journal.record_live_trade(db, body.model_dump())
        return {
            "status": "success",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "message": f"Transaksi live bot {trade.symbol} berhasil disimpan di Neonbase.",
        }
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_LIVE_TRADE", "message": str(e)}},
        )


@router.delete("/trades/{trade_id}")
def delete_journal_trade(trade_id: int, db: Session = Depends(get_db)):
    """Delete a trade record from the live journal."""
    success = journal.delete_live_trade(db, trade_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trade record tidak ditemukan.")
    return {"status": "deleted", "trade_id": trade_id}
