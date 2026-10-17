import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db, SessionLocal
from app.routers import auth, bot, portfolio, signals, ai, risk, performance, wallets, memecoins, journal, news, stocks, gold
from app.services import treasury


async def _daily_0500_wib_settlement_worker() -> None:
    """Background worker that checks every 30s if 05:00 WIB daily profit settlement is due."""
    while True:
        try:
            with SessionLocal() as db:
                treasury.check_and_run_0500_wib_schedule(db)
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_daily_0500_wib_settlement_worker())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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
app.include_router(gold.router, prefix="/api/v1/gold", tags=["Harga & Portofolio Emas"])


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "version": settings.version,
        "database": "neon-postgres" if "neon.tech" in settings.database_url else "postgres" if "postgresql" in settings.database_url else "sqlite",
    }
