"""Aggregates all v1 API routers under /api/v1."""

from app.api.v1 import (
    alerts,
    bot,
    market,
    performance,
    portfolio,
    providers,
    signals,
    system,
    wallets,
    watchlist,
)
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(market.router)
api_router.include_router(signals.router)
api_router.include_router(watchlist.router)
api_router.include_router(bot.router)
api_router.include_router(bot.risk_router)
api_router.include_router(portfolio.router)
api_router.include_router(providers.providers_router)
api_router.include_router(providers.router)
api_router.include_router(wallets.router)
api_router.include_router(performance.router)
api_router.include_router(performance.backtest_router)
api_router.include_router(alerts.router)

__all__ = ["api_router"]
