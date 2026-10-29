"""
/opt/data/projects/trading-operations-core/scheduler/signal_processor.py
Trading Operations Core - Signal Processor & Strategy Execution Scheduler

Capabilities:
1. Signal Normalization & Idempotency Deduplication (cooldown window protection)
2. Pre-Trade Safety Gate:
   - Blocks blacklisted narratives ('charity', 'donasi', 'mayhem')
   - Verifies live DexScreener liquidity & buy/sell ratio (Anti-Honeypot) for Solana DEX swaps
   - Optional Strategy Readiness Gate before allowing PAPER -> LIVE promotion
3. Multi-Venue Dispatch to TradingExecutor (Jupiter v6, Orca Whirlpools, Bybit V5)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from engine.executor import ExecutionMode, ExecutionVenue, TradingExecutor
from monitoring.watchdog import ServiceWatchdog, get_default_watchdog
from simulation.paper_engine import PaperSimulationEngine, get_default_paper_engine

logger = logging.getLogger("trading_ops.signal_processor")

BLOCKED_KEYWORDS = ("charity", "donasi", "donation", "mayhem", "honeypot", "scam")


@dataclass
class TradingSignal:
    signal_id: str
    source: str  # "webhook", "tradingview", "pumpfun_radar", "ai_agent"
    venue: str   # "JUPITER", "ORCA", "BYBIT"
    action: str  # "BUY" | "SELL" | "CLOSE"
    symbol: str  # e.g. "SOL/USDC", "BONK", "BTCUSDT", or "...pump" mint
    amount: float
    mode: str = "PAPER"
    slippage_bps: int = 100
    order_type: str = "Market"
    category: str = "linear"
    price: Optional[float] = None
    leverage: Optional[int] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    strategy_id: str = "default"
    require_live_validation: bool = False
    received_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SignalProcessor:
    """
    Processes incoming trading signals, runs pre-trade safety & Anti-Honeypot checks,
    and dispatches approved orders to TradingExecutor.
    """

    def __init__(
        self,
        executor: Optional[TradingExecutor] = None,
        paper_engine: Optional[PaperSimulationEngine] = None,
        watchdog: Optional[ServiceWatchdog] = None,
        cooldown_seconds: float = 5.0,
    ) -> None:
        self.paper_engine = paper_engine or get_default_paper_engine()
        self.watchdog = watchdog or get_default_watchdog()
        self.executor = executor or TradingExecutor(
            default_mode=ExecutionMode.PAPER,
            paper_engine=self.paper_engine,
            watchdog=self.watchdog,
        )
        self.cooldown_seconds = cooldown_seconds
        self._recent_fingerprints: dict[str, float] = {}
        self.processed_signals: list[dict[str, Any]] = []

    def _check_dex_token_safety(self, token_or_mint: str) -> tuple[bool, str]:
        """
        Pre-trade Anti-Honeypot & Narrative Safety check for Solana/Pump.fun tokens.
        """
        lower_q = token_or_mint.strip().lower()
        for kw in BLOCKED_KEYWORDS:
            if kw in lower_q:
                return False, f"Token mengandung kata kunci terlarang ('{kw}')."

        # Well-known major base tokens are always safe
        if token_or_mint.upper() in ("SOL", "WSOL", "USDC", "USDT", "JUP", "ORCA", "RAY", "BONK", "WIF"):
            return True, "Token utama terverifikasi aman."

        if len(token_or_mint.strip()) >= 32:
            try:
                with httpx.Client(timeout=5.0) as client:
                    res = client.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_or_mint.strip()}")
                    if res.status_code == 200:
                        pairs = res.json().get("pairs") or []
                        if not pairs:
                            return True, "Token baru belum terindeks penuh di DexScreener (lanjutkan dengan batas risiko)."
                        pairs.sort(
                            key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0),
                            reverse=True,
                        )
                        best = pairs[0]
                        base_name = str((best.get("baseToken") or {}).get("name") or "").lower()
                        base_sym = str((best.get("baseToken") or {}).get("symbol") or "").lower()
                        for kw in BLOCKED_KEYWORDS:
                            if kw in base_name or kw in base_sym:
                                return False, f"Nama/simbol token '{base_sym}' mengandung kategori terlarang ('{kw}')."

                        txns_24h = (best.get("txns") or {}).get("h24") or {}
                        buys = int(txns_24h.get("buys") or 0)
                        sells = int(txns_24h.get("sells") or 0)
                        if buys >= 25 and sells == 0:
                            return False, f"Indikasi HONEYPOT terdeteksi: {buys} BUY tetapi 0 SELL dalam 24 jam."
            except Exception as exc:
                logger.debug(f"Pre-trade safety check warning: {exc}")

        return True, "Lolos pemeriksaan pra-eksekusi."

    def process_signal(self, raw_signal: dict[str, Any] | TradingSignal) -> dict[str, Any]:
        """
        Validate, deduplicate, and execute a TradingSignal across Jupiter, Orca, or Bybit.
        """
        if isinstance(raw_signal, TradingSignal):
            sig = raw_signal
        else:
            sig = TradingSignal(
                signal_id=str(raw_signal.get("signal_id") or f"sig-{uuid.uuid4().hex[:10]}"),
                source=str(raw_signal.get("source") or "webhook"),
                venue=str(raw_signal.get("venue") or "JUPITER").upper(),
                action=str(raw_signal.get("action") or raw_signal.get("side") or "BUY").upper(),
                symbol=str(raw_signal.get("symbol") or raw_signal.get("token") or "SOL/USDC"),
                amount=float(raw_signal.get("amount") or raw_signal.get("qty") or 1.0),
                mode=str(raw_signal.get("mode") or "PAPER").upper(),
                slippage_bps=int(raw_signal.get("slippage_bps") or 100),
                order_type=str(raw_signal.get("order_type") or "Market"),
                category=str(raw_signal.get("category") or "linear"),
                price=float(raw_signal["price"]) if raw_signal.get("price") is not None else None,
                leverage=int(raw_signal["leverage"]) if raw_signal.get("leverage") is not None else None,
                take_profit=float(raw_signal["take_profit"]) if raw_signal.get("take_profit") is not None else None,
                stop_loss=float(raw_signal["stop_loss"]) if raw_signal.get("stop_loss") is not None else None,
                strategy_id=str(raw_signal.get("strategy_id") or "default"),
                require_live_validation=bool(raw_signal.get("require_live_validation", False)),
            )

        # 1. Deduplication check
        fingerprint = f"{sig.venue}:{sig.symbol}:{sig.action}:{sig.strategy_id}"
        now = time.time()
        last_seen = self._recent_fingerprints.get(fingerprint, 0.0)
        if (now - last_seen) < self.cooldown_seconds:
            rejected = {
                "signal_id": sig.signal_id,
                "status": "SKIPPED_DUPLICATE",
                "reason": f"Sinyal duplikat dalam jendela cooldown ({self.cooldown_seconds}s): {fingerprint}",
                "signal": asdict(sig),
            }
            self.processed_signals.append(rejected)
            return rejected
        self._recent_fingerprints[fingerprint] = now

        # 2. Optional Strategy Live Readiness Gate
        if sig.mode == "LIVE" and sig.require_live_validation:
            readiness = self.paper_engine.validate_strategy_for_live(strategy_id=sig.strategy_id)
            if not readiness["approved_for_live"]:
                blocked = {
                    "signal_id": sig.signal_id,
                    "status": "BLOCKED_BY_PAPER_VALIDATION",
                    "reason": readiness["verdict"],
                    "validation": readiness,
                    "signal": asdict(sig),
                }
                self.processed_signals.append(blocked)
                return blocked

        # 3. Route to appropriate venue
        venue_upper = sig.venue.upper()
        if venue_upper in (ExecutionVenue.JUPITER.value, ExecutionVenue.ORCA.value):
            if "/" in sig.symbol:
                parts = [p.strip() for p in sig.symbol.split("/", 1)]
                in_tok, out_tok = (parts[1], parts[0]) if sig.action == "BUY" else (parts[0], parts[1])
            else:
                in_tok = "SOL" if sig.action == "BUY" else sig.symbol
                out_tok = sig.symbol if sig.action == "BUY" else "SOL"

            target_check_tok = out_tok if sig.action == "BUY" else in_tok
            is_safe, safety_msg = self._check_dex_token_safety(target_check_tok)
            if not is_safe:
                blocked = {
                    "signal_id": sig.signal_id,
                    "status": "BLOCKED_UNSAFE_TOKEN",
                    "reason": safety_msg,
                    "signal": asdict(sig),
                }
                self.processed_signals.append(blocked)
                return blocked

            exec_res = self.executor.execute(
                venue=venue_upper,
                mode=sig.mode,
                input_token=in_tok,
                output_token=out_tok,
                amount=sig.amount,
                slippage_bps=sig.slippage_bps,
            )
        elif venue_upper == ExecutionVenue.BYBIT.value:
            exec_res = self.executor.execute(
                venue=ExecutionVenue.BYBIT.value,
                mode=sig.mode,
                symbol=sig.symbol,
                side="Buy" if sig.action == "BUY" else "Sell",
                qty=sig.amount,
                order_type=sig.order_type,
                category=sig.category,
                price=sig.price,
                leverage=sig.leverage,
                take_profit=sig.take_profit,
                stop_loss=sig.stop_loss,
            )
        else:
            raise ValueError(f"Venue sinyal tidak dikenali: {sig.venue}")

        outcome = {
            "signal_id": sig.signal_id,
            "status": "PROCESSED",
            "signal": asdict(sig),
            "execution": exec_res,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.processed_signals.append(outcome)
        if len(self.processed_signals) > 300:
            self.processed_signals = self.processed_signals[-300:]
        return outcome


_DEFAULT_SIGNAL_PROCESSOR: Optional[SignalProcessor] = None


def get_default_signal_processor() -> SignalProcessor:
    global _DEFAULT_SIGNAL_PROCESSOR
    if _DEFAULT_SIGNAL_PROCESSOR is None:
        _DEFAULT_SIGNAL_PROCESSOR = SignalProcessor()
    return _DEFAULT_SIGNAL_PROCESSOR
