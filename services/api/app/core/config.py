from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SOFIA_", extra="ignore")

    app_name: str = "Next Gent Sofia Trade v1"
    engine_version: str = "1.0.0"
    scoring_config_version: str = "scoring-v1"
    risk_rule_version: str = "risk-v1"
    env: str = "development"

    database_url: str = "sqlite:///./data/sofia_trade.db"

    # Authentication is ON by default (PRD 3.3: never expose admin API without
    # auth). Disabling it requires an explicit opt-in and is refused outside
    # development (see `app.main.create_app` startup guard).
    auth_disabled: bool = False
    admin_password_hash: str = ""  # pbkdf2_sha256$iters$salt$hash
    admin_password: str = "change-me-in-production"  # legacy plaintext fallback
    observer_password_hash: str = ""
    observer_password: str = ""
    session_ttl_seconds: int = 8 * 3600
    internal_signature_key: str = ""  # empty => internal signing disabled

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    live_trading_enabled: bool = False  # V1 gate: ALWAYS false. Server rejects live start.

    dexscreener_base_url: str = "https://api.dexscreener.com"
    dexscreener_rate_limit_per_min: int = 60
    dexscreener_search_rate_limit_per_min: int = 60
    dexscreener_tokens_rate_limit_per_min: int = 60
    market_cache_ttl_seconds: int = 30
    market_stale_after_seconds: int = 300

    # How old a price may be before an open position stops being valued.
    # A stale mark is reported as STALE (unknown PnL), never as 0.
    position_mark_stale_after_seconds: int = 300

    # Fallback exit plan for a position whose signal carries no stop or target.
    # The signal's own plan always wins; these only apply when it is silent.
    position_stop_loss_pct: float = 8.0
    position_take_profit_pct: float = 20.0
    # How long a position may sit in CLOSING before recovery reclaims it.
    position_exit_recovery_seconds: int = 300

    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    solana_rpc_rate_limit_per_min: int = 120

    ninrouter_base_url: str = "https://9router.com/v1"
    ninrouter_api_key: str = ""
    ninrouter_model: str = ""

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openrouter_default_model: str = "openrouter/free"
    llm_timeout_seconds: float = 30.0

    # Cross-provider fallback is OFF by default (FR §9.4). When enabled, the
    # candidate order is explicit configuration and every candidate still has
    # to pass the provider's own model gate - a fallback never buys its way
    # around the free-only policy.
    llm_cross_provider_fallback: bool = False
    llm_provider_order: str = "openrouter,9router"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    worker_scanner_interval: int = 60
    worker_analysis_interval: int = 120
    worker_signal_eval_interval: int = 60

    initial_paper_capital: float = 1000.0
    idr_rate: float = 16300.0

    # Scanner filters (configurable discovery thresholds, FR-AE-001)
    scanner_min_liquidity_usd: float = 10000.0
    scanner_min_pool_age_minutes: float = 60.0
    scanner_min_volume_24h_usd: float = 0.0
    scanner_min_txns_1h: int = 0
    scanner_min_abs_price_change_1h_pct: float = 0.0
    scanner_allow_incomplete: bool = False
    scanner_max_results: int = 40

    @field_validator(
        "live_trading_enabled",
        "auth_disabled",
        mode="before",
    )
    @classmethod
    def _coerce_bool(cls, v):  # noqa: ANN001
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return v

    @field_validator("session_ttl_seconds", mode="after")
    @classmethod
    def _positive_ttl(cls, v: int) -> int:  # noqa: N805
        if v <= 0:
            raise ValueError("session_ttl_seconds must be positive")
        return v

    # Fields whose values must never reach a log, an API response, or an error
    # body. `safe_dump()` and `__repr__` redact these; the raw `model_dump()`
    # remains available for code that genuinely needs the value.
    SECRET_FIELDS: frozenset[str] = frozenset(
        {
            "admin_password",
            "admin_password_hash",
            "observer_password",
            "observer_password_hash",
            "openrouter_api_key",
            "ninrouter_api_key",
            "internal_signature_key",
            "telegram_bot_token",
        }
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_fallback_order(self) -> list[str]:
        """Provider preference used only when cross-provider fallback is enabled.

        Order is explicit configuration, never inferred from which key happens to
        be present, so automatic routing stays predictable (FR §9.6).
        """
        return [p.strip() for p in self.llm_provider_order.split(",") if p.strip()]

    def safe_dump(self, redact: bool = True) -> dict:
        """Settings as a dict, with credential material removed by default.

        Use this for diagnostics, health output and anything that could be
        logged. `model_dump()` returns live secrets and must not be exposed.
        """
        data = self.model_dump()
        if not redact:
            return data
        for name in self.SECRET_FIELDS:
            if name in data and data[name]:
                data[name] = "***redacted***"
        return data

    def __repr__(self) -> str:  # noqa: D105 - keep secrets out of tracebacks
        return f"{type(self).__name__}({self.safe_dump()!r})"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
