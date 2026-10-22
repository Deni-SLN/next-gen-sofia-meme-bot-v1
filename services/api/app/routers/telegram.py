from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services import telegram_radar
from app.core.security import get_current_user

router = APIRouter()


class SendAlertRequest(BaseModel):
    token: str
    chat_id: str
    message: Optional[str] = None


@router.get("/bots")
def list_telegram_bots(category: Optional[str] = Query(None, description="AUDIT_SAFETY | SMART_MONEY | CHART_PRICE | WHALE_RADAR | IDX_STOCKS")):
    """List verified publicly available Telegram analysis and radar bots."""
    bots = telegram_radar.get_public_bots(category)
    return {
        "status": "success",
        "total": len(bots),
        "bots": bots,
    }


@router.get("/query-links")
def get_bot_query_links(
    symbol: str = Query("SOL", description="Ticker or coin symbol"),
    contract: Optional[str] = Query(None, description="Solana Mint Address or Contract"),
):
    """Generate 1-click Telegram deep-links with pre-filled query commands."""
    links = telegram_radar.generate_bot_query_links(symbol, contract)
    return {
        "status": "success",
        "symbol": symbol.upper(),
        "contract": contract,
        "query_links": links,
    }


@router.get("/signals")
def get_telegram_alpha_signals():
    """Retrieve live signals aggregated from public Telegram community radars."""
    signals = telegram_radar.get_public_alpha_signals()
    return {
        "status": "success",
        "total": len(signals),
        "signals": signals,
    }


@router.post("/test-alert")
def send_test_alert(body: SendAlertRequest, user=Depends(get_current_user)):
    """Send a test notification message to the user's Telegram."""
    msg = body.message or (
        "🚀 <b>Sofia Market 3.9 — Tes Notifikasi Telegram Berhasil!</b>\n\n"
        "Bot Telegram Anda telah terhubung sempurna dengan Sofia Market 3.9.\n"
        "Notifikasi Sniper, TP/SL, dan sinyal pasar akan dikirimkan ke sini secara real-time."
    )
    result = telegram_radar.send_telegram_alert(
        token=body.token,
        chat_id=body.chat_id,
        text=msg,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result
