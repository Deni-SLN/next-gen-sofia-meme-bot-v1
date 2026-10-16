import os
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"
_API_ENV = Path(__file__).resolve().parents[2] / ".env"
_DEFAULT_NEON_URL = (
    "postgresql+psycopg://neondb_owner:npg_RDIYro7b4CsM@"
    "ep-weathered-forest-aomnfoor-pooler.c-2.ap-southeast-1.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql+psycopg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+psycopg://" + u[len("postgresql://") :]
    return u


class Settings(BaseSettings):
    app_name: str = "NextGenTSofia Trade"
    version: str = "1.0.0"
    debug: bool = False
    database_url: str = _DEFAULT_NEON_URL
    admin_password: str = "changeme"
    jwt_secret: str = "sofia-super-secret-key-change-in-production-12345"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openrouter_default_model: str = "anthropic/claude-3.5-sonnet"
    llm_timeout_seconds: int = 30
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=[str(_ROOT_ENV), str(_API_ENV), ".env"],
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


settings = Settings()
