import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db, SessionLocal
from app.routers import auth, bot, portfolio, signals, ai, risk, performance, wallets, memecoins, journal, news, stocks, gold, crypto, chat, telegram, mcp as mcp_router
from app.mcp_server import mcp
from app.services import treasury, bot as bot_service


async def _daily_0500_wib_settlement_worker() -> None:
    """Background worker that checks every 30s if 05:00 WIB daily profit settlement is due."""
    while True:
        try:
            with SessionLocal() as db:
                treasury.check_and_run_0500_wib_schedule(db)
        except Exception:
            pass
        await asyncio.sleep(30)


def _execute_background_bot_tick() -> float:
    """Run one synchronous bot scan/trade tick if bot status is 'running', returning next sleep interval."""
    with SessionLocal() as db:
        state = bot_service.get_bot_status(db)
        cfg = bot_service.get_sniper_config()
        interval_sec = max(1.5, float(cfg.get("tick_interval_ms", 3000)) / 1000.0)
        if state.status == "running":
            bot_service.run_bot_scan_tick(db, auto_trade=True, force_trade=False)
        return interval_sec


async def _autonomous_bot_engine_worker() -> None:
    """Autonomous background engine so the bot keeps scanning and trading across menu changes, closed tabs, or logout until explicitly stopped."""
    while True:
        sleep_sec = 2.5
        try:
            sleep_sec = await asyncio.wait_for(asyncio.to_thread(_execute_background_bot_tick), timeout=25.0)
        except Exception:
            sleep_sec = 3.0
        await asyncio.sleep(sleep_sec)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bot_service.ensure_autonomous_bot_daemon()
    settlement_task = asyncio.create_task(_daily_0500_wib_settlement_worker())
    bot_engine_task = asyncio.create_task(_autonomous_bot_engine_worker())
    try:
        yield
    finally:
        settlement_task.cancel()
        bot_engine_task.cancel()
        with suppress(asyncio.CancelledError):
            await settlement_task
        with suppress(asyncio.CancelledError):
            await bot_engine_task


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(bot.router, prefix="/api/v1/bot", tags=["Bot"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["Signals"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Agents"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["Performance"])
app.include_router(wallets.router, prefix="/api/v1/wallets", tags=["Wallets"])
app.include_router(memecoins.router, prefix="/api/v1/memecoins", tags=["Meme Coin Sniper"])
app.include_router(journal.router, prefix="/api/v1/journal", tags=["Live Trading Journal"])
app.include_router(news.router, prefix="/api/v1/news", tags=["Berita Indonesia"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["Analisa Saham BEI"])
app.include_router(crypto.router, prefix="/api/v1/crypto", tags=["Analisa Crypto Global"])
app.include_router(gold.router, prefix="/api/v1/gold", tags=["Harga & Portofolio Emas"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Chat & Research"])
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["Telegram Bot & Radar"])
app.include_router(mcp_router.router, prefix="/api/v1/mcp", tags=["Model Context Protocol (MCP)"])

# Mount FastMCP SSE Endpoint for Hermes Agent, OpenClaw, and Networked MCP Clients
app.mount("/mcp", mcp.sse_app())


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "version": settings.version,
        "database": "neon-postgres" if "neon.tech" in settings.database_url else "postgres" if "postgresql" in settings.database_url else "sqlite",
    }
