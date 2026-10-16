"""Next Gent Sofia Trade v1 API application factory."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging

setup_logging()
log = logging.getLogger("sofia")

REQUEST_ID_HEADER = "X-Request-ID"
MAX_INBOUND_REQUEST_ID_LEN = 64
DEV_ENVS = {"development", "test", "local"}


def _incoming_request_id(request: Request) -> str:
    """Reuse a caller-supplied correlation id when it is safe to echo back."""
    supplied = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if supplied and len(supplied) <= MAX_INBOUND_REQUEST_ID_LEN:
        # Only a conservative charset is echoed; anything else is replaced.
        if all(ch.isalnum() or ch in "-_.:" for ch in supplied):
            return supplied
    return uuid.uuid4().hex


def create_app() -> FastAPI:
    app = FastAPI(
        title="Next Gent Sofia Trade v1 API",
        version="1.0.0",
        description=(
            "Solana Meme Coin Intelligence & Trading Platform. "
            "Analysis-only and PAPER by default; LIVE is disabled in V1."
        ),
        openapi_tags=[
            {"name": "system", "description": "Auth and system health"},
            {"name": "market", "description": "Market discovery and token data"},
            {"name": "signals", "description": "Signal center and analysis history"},
            {"name": "watchlist", "description": "Watchlists"},
            {"name": "bot", "description": "Trading bot control (PAPER/LIVE disabled)"},
            {"name": "risk", "description": "Risk configuration"},
            {"name": "portfolio", "description": "Portfolio and accounting"},
            {"name": "wallets", "description": "Wallets, transfers and profit sweep"},
            {"name": "providers", "description": "Market data provider status"},
            {"name": "ai", "description": "AI agents, model registry, usage"},
            {"name": "performance", "description": "Performance metrics and backtest"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # noqa: ANN001
        """Attach a correlation id and echo it back in X-Request-ID (PRD §12.6)."""
        request.state.request_id = _incoming_request_id(request)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            log.exception(
                "unhandled %s %s duration_ms=%.1f request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request.state.request_id,
            )
            raise  # the registered handler builds the envelope
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        log.info(
            "%s %s -> %s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request.state.request_id,
        )
        return response

    register_exception_handlers(app)

    @app.on_event("startup")
    def _startup() -> None:
        _check_safety_settings()

        log.info(
            "starting %s (env=%s, auth_disabled=%s, live_trading=%s)",
            settings.app_name,
            settings.env,
            settings.auth_disabled,
            settings.live_trading_enabled,
        )
        # Development convenience only; Alembic owns real migrations.
        from app.db.session import init_db

        try:
            init_db()
        except Exception:  # noqa: BLE001
            log.exception("init_db failed on startup")

    app.include_router(api_router)
    return app


def _check_safety_settings() -> None:
    """Refuse to serve a configuration that breaks a PRD safety rule."""
    if settings.auth_disabled and settings.env not in DEV_ENVS:
        raise RuntimeError(
            "SOFIA_AUTH_DISABLED=true is only allowed when SOFIA_ENV is "
            f"development/test/local (current: {settings.env!r}). Refusing to start."
        )
    if not settings.auth_disabled and not (
        settings.admin_password_hash or settings.admin_password
    ):
        raise RuntimeError("No admin credential configured: set SOFIA_ADMIN_PASSWORD_HASH.")
    if settings.live_trading_enabled:
        # PRD §16: live trading is not a V1 capability.
        raise RuntimeError(
            "SOFIA_LIVE_TRADING_ENABLED=true is not permitted in V1; live trading "
            "stays feature-gated off until the separate approval gate is opened."
        )


app = create_app()