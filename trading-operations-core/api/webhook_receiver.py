"""
/opt/data/projects/trading-operations-core/api/webhook_receiver.py
Trading Operations Core - Webhook Signal Receiver & Multi-Venue API

Provides:
- HMAC-SHA256 authenticated webhook ingestion (`/webhook/signal`, `/webhook/tradingview`)
- Direct execution endpoints for Jupiter v6, Orca Whirlpools, and Bybit V5
- Paper Simulation portfolio & LIVE readiness validation endpoints
- Watchdog health probes & KPI monitoring knob tuning endpoints
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from scheduler.signal_processor import SignalProcessor, get_default_signal_processor


class WebhookSignalPayload(BaseModel):
    signal_id: Optional[str] = None
    source: str = Field(default="webhook", description="Signal origin: webhook, tradingview, pumpfun_radar")
    venue: str = Field(default="JUPITER", description="Target venue: JUPITER, ORCA, BYBIT")
    action: str = Field(default="BUY", description="BUY or SELL")
    symbol: str = Field(..., description="Pair or token mint e.g. SOL/USDC, BONK, BTCUSDT, or ...pump")
    amount: float = Field(..., gt=0, description="Input token amount (DEX) or base order qty (Bybit)")
    mode: str = Field(default="PAPER", description="PAPER or LIVE")
    slippage_bps: int = Field(default=100, ge=1, le=5000)
    order_type: str = Field(default="Market")
    category: str = Field(default="linear")
    price: Optional[float] = None
    leverage: Optional[int] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    strategy_id: str = Field(default="default")
    require_live_validation: bool = Field(default=False)
    passphrase: Optional[str] = None


class JupiterSwapRequest(BaseModel):
    input_token: str = Field(..., description="Input symbol or mint e.g. SOL, USDC")
    output_token: str = Field(..., description="Output symbol or mint e.g. BONK, WIF, ...pump")
    amount: float = Field(..., gt=0)
    slippage_bps: int = Field(default=100, ge=1, le=5000)
    mode: str = Field(default="PAPER")


class OrcaSwapRequest(BaseModel):
    input_token: str = Field(..., description="Input symbol or mint e.g. SOL, USDC")
    output_token: str = Field(..., description="Output symbol or mint e.g. ORCA, BONK")
    amount: float = Field(..., gt=0)
    slippage_bps: int = Field(default=50, ge=1, le=5000)
    whirlpool_address: Optional[str] = None
    tick_spacing: int = Field(default=64)
    mode: str = Field(default="PAPER")


class BybitOrderRequest(BaseModel):
    symbol: str = Field(..., description="Bybit symbol e.g. BTCUSDT, SOLUSDT")
    side: str = Field(default="Buy", description="Buy or Sell")
    qty: float = Field(..., gt=0)
    order_type: str = Field(default="Market", description="Market or Limit")
    category: str = Field(default="linear", description="spot, linear, or inverse")
    price: Optional[float] = None
    leverage: Optional[int] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    mode: str = Field(default="PAPER")
    testnet: bool = Field(default=False)


class KPIKnobsUpdateRequest(BaseModel):
    max_daily_drawdown_pct: Optional[float] = None
    max_consecutive_failures: Optional[int] = None
    max_rpc_latency_ms: Optional[float] = None
    max_slippage_drift_bps: Optional[int] = None
    min_acceptable_fill_rate_pct: Optional[float] = None
    auto_kill_switch_enabled: Optional[bool] = None


def verify_webhook_hmac(raw_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature if a secret is configured."""
    if not secret:
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    clean_sig = signature_header.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, clean_sig)


def create_webhook_router(processor: Optional[SignalProcessor] = None) -> APIRouter:
    router = APIRouter(tags=["Trading Operations Core Engine"])
    sig_proc = processor or get_default_signal_processor()

    @router.post("/webhook/signal")
    async def receive_webhook_signal(
        payload: WebhookSignalPayload,
        request: Request,
        x_sofia_signature: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        secret = os.environ.get("SOFIA_WEBHOOK_SECRET", "").strip()
        if secret:
            raw_body = await request.body()
            if not verify_webhook_hmac(raw_body, x_sofia_signature, secret):
                if payload.passphrase != secret:
                    raise HTTPException(status_code=401, detail="Signature webhook HMAC tidak valid.")

        return sig_proc.process_signal(payload.model_dump())

    @router.post("/execute/jupiter")
    def api_execute_jupiter(req: JupiterSwapRequest) -> dict[str, Any]:
        return sig_proc.executor.execute(
            venue="JUPITER",
            mode=req.mode,
            input_token=req.input_token,
            output_token=req.output_token,
            amount=req.amount,
            slippage_bps=req.slippage_bps,
        )

    @router.post("/execute/orca")
    def api_execute_orca(req: OrcaSwapRequest) -> dict[str, Any]:
        return sig_proc.executor.execute(
            venue="ORCA",
            mode=req.mode,
            input_token=req.input_token,
            output_token=req.output_token,
            amount=req.amount,
            slippage_bps=req.slippage_bps,
            whirlpool_address=req.whirlpool_address,
            tick_spacing=req.tick_spacing,
        )

    @router.post("/execute/bybit")
    def api_execute_bybit(req: BybitOrderRequest) -> dict[str, Any]:
        return sig_proc.executor.execute(
            venue="BYBIT",
            mode=req.mode,
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            order_type=req.order_type,
            category=req.category,
            price=req.price,
            leverage=req.leverage,
            take_profit=req.take_profit,
            stop_loss=req.stop_loss,
            testnet=req.testnet,
        )

    @router.get("/paper/portfolio")
    def api_get_paper_portfolio() -> dict[str, Any]:
        return sig_proc.paper_engine.get_portfolio_summary()

    @router.post("/paper/validate-live")
    def api_validate_strategy_for_live(
        strategy_id: Optional[str] = None,
        min_closed_trades: int = 5,
        min_win_rate_pct: float = 52.0,
        min_profit_factor: float = 1.25,
        max_allowed_drawdown_pct: float = 15.0,
    ) -> dict[str, Any]:
        return sig_proc.paper_engine.validate_strategy_for_live(
            strategy_id=strategy_id,
            min_closed_trades=min_closed_trades,
            min_win_rate_pct=min_win_rate_pct,
            min_profit_factor=min_profit_factor,
            max_allowed_drawdown_pct=max_allowed_drawdown_pct,
        )

    @router.get("/watchdog/kpi")
    def api_get_watchdog_kpi() -> dict[str, Any]:
        return sig_proc.watchdog.get_kpi_dashboard(paper_engine=sig_proc.paper_engine)

    @router.post("/watchdog/knobs")
    def api_update_watchdog_knobs(req: KPIKnobsUpdateRequest) -> dict[str, Any]:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return sig_proc.watchdog.update_knobs(**updates)

    @router.post("/watchdog/probe")
    def api_run_watchdog_probe() -> dict[str, Any]:
        return sig_proc.watchdog.run_venue_health_probes()

    @router.post("/watchdog/reset")
    def api_reset_watchdog() -> dict[str, Any]:
        return sig_proc.watchdog.reset_circuit_breaker()

    return router
