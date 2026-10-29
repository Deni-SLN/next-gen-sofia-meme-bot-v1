import os
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[4]
_API_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_NEON_URL = "sqlite:///./sofia_trade.db"


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql+psycopg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+psycopg://" + u[len("postgresql://") :]
    return u


class Settings(BaseSettings):
    app_name: str = "Sofia Market 4.1.2"
    version: str = "4.1.2"
    debug: bool = False
    database_url: str = _DEFAULT_NEON_URL
    admin_password: str = "changeme"
    primary_username: str = "Deni26"
    primary_password: str = "Ronaldo07@"
    jwt_secret: str = "sofia-super-secret-key-change-in-production-12345"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-3.5-sonnet"
    llm_timeout_seconds: int = 30
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Solana On-Chain Trading, FluxRPC & Flux Shield (Powered by FluxBeam / RugCheck)
    solana_rpc_url: str = "https://eu.fluxrpc.com?key=24252d08-b2ec-4d3f-8baf-9650199b77a9"
    solana_shield_rpc_url: str = "https://eu.shield.fluxrpc.com?key=QrpekiPs1SeekuEwSi_25A"
    solana_ws_url: str = "wss://ws.eu.fluxrpc.com"
    fluxrpc_api_key: str = "24252d08-b2ec-4d3f-8baf-9650199b77a9"
    fluxrpc_shield_key: str = "QrpekiPs1SeekuEwSi_25A"
    solana_private_key: str = ""
    solana_trading_private_key: str = ""
    solana_trading_address: str = ""
    solana_main_private_key: str = ""
    solana_main_address: str = ""
    solana_reserve_seed: str = ""
    solana_reserve_address: str = ""
    live_trading_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=[
            str(_ROOT_DIR / ".env.local"),
            str(_ROOT_DIR / ".env"),
            str(_API_DIR / ".env.local"),
            str(_API_DIR / ".env"),
            ".env.local",
            ".env",
        ],
        env_prefix="SOFIA_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        env_db = os.environ.get("SOFIA_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if env_db:
            self.database_url = _normalize_db_url(env_db)
        else:
            self.database_url = _normalize_db_url(self.database_url)
        return self

    @model_validator(mode="after")
    def resolve_wallet_aliases(self) -> "Settings":
        legacy_priv = (self.solana_private_key or os.environ.get("SOFIA_SOLANA_PRIVATE_KEY") or "").strip()
        if legacy_priv and not self.solana_trading_private_key:
            self.solana_trading_private_key = legacy_priv
        return self


settings = Settings()
