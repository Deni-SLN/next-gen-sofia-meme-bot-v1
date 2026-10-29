"""
/opt/data/projects/trading-operations-core/main.py
Trading Operations Core Engine (v4.1.3)
Implements all execution paths: Jupiter v6, Orca Whirlpools, Bybit V5 CEX,
Paper Simulation Engine, Signal Processor, Service Watchdog, and Webhook Receiver.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure package root is on sys.path whether invoked from /opt/data/projects/trading-operations-core or workspace
CORE_ROOT = Path(__file__).resolve().parent
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from fastapi import FastAPI

from api.webhook_receiver import create_webhook_router
from engine.executor import (
    ExecutionMode,
    ExecutionVenue,
    TradingExecutor,
    execute_bybit_order,
    execute_jupiter_swap,
    execute_orca_swap,
)
from monitoring.watchdog import ServiceWatchdog, WatchdogKPIKnobs, get_default_watchdog
from scheduler.signal_processor import SignalProcessor, get_default_signal_processor
from simulation.paper_engine import PaperSimulationEngine, get_default_paper_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trading_ops.main")


def create_core_app() -> FastAPI:
    """Create standalone FastAPI application for Trading Operations Core Engine."""
    app = FastAPI(
        title="Sofia Trading Operations Core Engine",
        version="4.1.3",
        description=(
            "Multi-Venue Execution Core (Jupiter v6, Orca Whirlpools CLMM, Bybit V5 CEX) "
            "with isolated Paper Simulation Engine, Webhook Signal Processor, and KPI Watchdog."
        ),
    )
    app.include_router(create_webhook_router(), prefix="/api/v1/trading-ops")

    @app.get("/health")
    def health() -> dict[str, Any]:
        wd = get_default_watchdog()
        pe = get_default_paper_engine()
        return {
            "status": "ok",
            "version": "4.1.3",
            "engine": "trading-operations-core",
            "venues": ["JUPITER", "ORCA", "BYBIT"],
            "circuit_breaker_tripped": wd.circuit_breaker_tripped,
            "paper_equity_usd": pe.get_portfolio_summary()["total_equity_usd"],
        }

    return app


app = create_core_app()


def run_self_test() -> dict[str, Any]:
    """
    Execute an end-to-end verification suite across all 5 core components in PAPER mode
    using live market quotes from Jupiter v6, Orca Whirlpools, and Bybit V5.
    """
    paper = get_default_paper_engine()
    watchdog = get_default_watchdog()
    processor = get_default_signal_processor()

    # 1. Venue Health Probes
    probes = watchdog.run_venue_health_probes()

    # 2. Jupiter v6 Swap (SOL -> BONK)
    jup_buy = execute_jupiter_swap(
        input_token="SOL",
        output_token="BONK",
        amount=0.5,
        slippage_bps=100,
        mode=ExecutionMode.PAPER,
        paper_engine=paper,
    )
    watchdog.record_execution_event(jup_buy)

    # 3. Orca Whirlpools CLMM Swap (SOL -> USDC)
    orca_swap = execute_orca_swap(
        input_token="SOL",
        output_token="USDC",
        amount=0.25,
        slippage_bps=50,
        mode=ExecutionMode.PAPER,
        paper_engine=paper,
    )
    watchdog.record_execution_event(orca_swap)

    # 4. Bybit V5 Linear Perp Order (SOLUSDT Buy & Partial Close)
    bybit_open = execute_bybit_order(
        symbol="SOLUSDT",
        side="Buy",
        qty=2.0,
        order_type="Market",
        category="linear",
        leverage=5,
        mode=ExecutionMode.PAPER,
        paper_engine=paper,
    )
    watchdog.record_execution_event(bybit_open)

    # 5. Webhook Signal Processor Test (including Anti-Charity/Honeypot safety block check)
    sig_valid = processor.process_signal({
        "source": "webhook",
        "venue": "BYBIT",
        "action": "SELL",
        "symbol": "SOLUSDT",
        "amount": 1.0,
        "mode": "PAPER",
        "category": "linear",
        "strategy_id": "momentum_v1",
    })
    sig_blocked = processor.process_signal({
        "source": "pumpfun_radar",
        "venue": "JUPITER",
        "action": "BUY",
        "symbol": "CharityDonasiScamToken",
        "amount": 0.1,
        "mode": "PAPER",
    })

    return {
        "engine_version": "4.1.3",
        "health_probes": probes,
        "executions": {
            "jupiter_v6_swap": {
                "execution_id": jup_buy["execution_id"],
                "status": jup_buy["status"],
                "amount_in_sol": jup_buy["amount_in"],
                "amount_out_bonk": jup_buy["amount_out"],
                "fee_usd": jup_buy["fee_usd"],
                "latency_ms": jup_buy["latency_ms"],
            },
            "orca_whirlpool_swap": {
                "execution_id": orca_swap["execution_id"],
                "status": orca_swap["status"],
                "amount_in_sol": orca_swap["amount_in"],
                "amount_out_usdc": orca_swap["amount_out"],
                "fee_usd": orca_swap["fee_usd"],
                "whirlpool": orca_swap.get("metadata", {}).get("orca_whirlpool", {}).get("whirlpool_address"),
                "latency_ms": orca_swap["latency_ms"],
            },
            "bybit_v5_order": {
                "execution_id": bybit_open["execution_id"],
                "status": bybit_open["status"],
                "symbol": bybit_open["symbol_or_pair"],
                "execution_price": bybit_open["execution_price"],
                "fee_usd": bybit_open["fee_usd"],
                "latency_ms": bybit_open["latency_ms"],
            },
        },
        "signal_processor": {
            "valid_signal_status": sig_valid["status"],
            "blocked_unsafe_signal_status": sig_blocked["status"],
            "blocked_reason": sig_blocked.get("reason"),
        },
        "paper_portfolio": paper.get_portfolio_summary(),
        "live_readiness_validation": paper.validate_strategy_for_live(strategy_id="momentum_v1"),
        "watchdog_kpi": watchdog.get_kpi_dashboard(paper_engine=paper),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading Operations Core Engine CLI")
    parser.add_argument("--self-test", action="store_true", help="Run live quote & paper execution self-test")
    parser.add_argument("--serve", action="store_true", help="Run standalone FastAPI webhook & execution server")
    parser.add_argument("--port", type=int, default=8090, help="Port for standalone server")
    args = parser.parse_args()

    if args.self_test:
        report = run_self_test()
        print(json.dumps(report, indent=2))
    elif args.serve:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        report = run_self_test()
        print(json.dumps(report, indent=2))
