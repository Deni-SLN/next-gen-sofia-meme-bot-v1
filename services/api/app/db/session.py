from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.models import (
    Base,
    BotState,
    RiskConfig,
    AIAgent,
    Wallet,
    PortfolioHolding,
    Signal,
    TreasuryState,
    Trade,
    GoldHolding,
    StockPortfolioPosition,
    StockWatchlistItem,
    StockSignalJournal,
    ChatSession,
    ChatMessage,
)

connect_args = {}
engine_kwargs: dict = {"echo": settings.debug}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # Neon Postgres pooled endpoint best practices: recycle & pre-ping on scale-to-zero wakeups
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 180
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column_migrations() -> None:
    """Ensure new columns exist on existing tables (both Postgres and SQLite)."""
    alter_statements = [
        ("trades", "market_price", "FLOAT DEFAULT 0.0"),
        ("trades", "slippage_pct", "FLOAT DEFAULT 0.0"),
        ("trades", "dex_fee_usd", "FLOAT DEFAULT 0.0"),
        ("trades", "gas_fee_usd", "FLOAT DEFAULT 0.0"),
        ("trades", "chain", "VARCHAR(30) DEFAULT 'Solana'"),
        ("trades", "tx_hash", "VARCHAR(100) DEFAULT ''"),
        ("trades", "notes", "TEXT DEFAULT ''"),
        ("portfolio_holdings", "entry_costs_usd", "FLOAT DEFAULT 0.0"),
        ("portfolio_holdings", "liquidity_usd", "FLOAT DEFAULT 0.0"),
        ("portfolio_holdings", "mode", "VARCHAR(10) DEFAULT 'PAPER'"),
    ]
    is_pg = not settings.database_url.startswith("sqlite")
    with engine.begin() as conn:
        for table_name, col_name, col_def in alter_statements:
            try:
                if is_pg:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_def}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass

        if is_pg:
            try:
                conn.execute(text("ALTER TABLE settlements ALTER COLUMN trigger TYPE VARCHAR(100)"))
                conn.execute(text("ALTER TABLE settlements ALTER COLUMN status TYPE VARCHAR(50)"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS portfolio_holdings_symbol_key"))
                conn.execute(text("DROP INDEX IF EXISTS ix_portfolio_holdings_symbol"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_holdings_symbol_mode ON portfolio_holdings (symbol, mode)"))
            except Exception:
                pass
        else:
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_portfolio_holdings_symbol"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_holdings_symbol_mode ON portfolio_holdings (symbol, mode)"))
            except Exception:
                pass


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_column_migrations()

    with SessionLocal() as db:
        # 1. Bot State singleton
        state = db.execute(select(BotState).where(BotState.id == 1)).scalar_one_or_none()
        if not state:
            state = BotState(id=1, status="idle", mode="PAPER", total_trades=0)
            db.add(state)

        # 2. Risk Config singleton (Meme Coin defaults)
        risk = db.execute(select(RiskConfig).where(RiskConfig.id == 1)).scalar_one_or_none()
        if not risk:
            risk = RiskConfig(
                id=1,
                max_position_size_pct=5.0,
                max_daily_loss_pct=3.0,
                max_drawdown_pct=15.0,
                stop_loss_pct=12.0,
                take_profit_pct=45.0,
                max_open_positions=10,
                allowed_symbols=["WIF/USDT", "POPCAT/USDT", "PEPEAI/SOL", "PNUT2/SOL", "BRETT/USDT", "BONK/USDT"],
            )
            db.add(risk)

        # 3. Default Meme Coin AI Agents
        existing_agent = db.execute(select(AIAgent).limit(1)).scalar_one_or_none()
        if not existing_agent:
            agents = [
                AIAgent(
                    name="Pump.fun Graduation Sniper AI",
                    description="Detects bonding curve velocity >85% and auto-snipes Raydium migration with Jito anti-MEV",
                    agent_type="signal",
                    status="active",
                    output_schema={"type": "object", "properties": {"confidence": {"type": "number"}}},
                    config={"min_liquidity": 12000, "max_bundle_pct": 10.0},
                ),
                AIAgent(
                    name="Rug & Insider Bundle Shield",
                    description="Scans block-0 sniper bundles, dev wallet concentration, mint/freeze authority, and LP burn status",
                    agent_type="risk",
                    status="active",
                    output_schema={"type": "object", "properties": {"safe": {"type": "boolean"}}},
                    config={"max_top10_pct": 25.0, "require_mint_revoked": True},
                ),
                AIAgent(
                    name="CT / X Meme Narrative Scanner",
                    description="Tracks viral ticker velocity on Crypto Twitter & Telegram alpha groups in real time",
                    agent_type="analyst",
                    status="active",
                    output_schema={"type": "object", "properties": {"sentiment_score": {"type": "number"}}},
                    config={"window_minutes": 5},
                ),
            ]
            db.add_all(agents)

        # 4. Treasury State singleton (Auto Top-Up Gas Fee & 05:00 WIB 40%/60% Profit Settlement)
        treasury = db.execute(select(TreasuryState).where(TreasuryState.id == 1)).scalar_one_or_none()
        if not treasury:
            treasury = TreasuryState(
                id=1,
                gas_reserve_usd=0.30,  # ~Rp 5.000 initial gas reserve
                gas_min_idr=3000.0,
                gas_target_idr=7500.0,
                baseline_equity_usd=9.0,  # updated dynamically with live fx
                baseline_set_at=datetime.now(timezone.utc),
                profit_threshold_pct=40.0,
                main_share_pct=40.0,
                paper_main_vault_usd=0.0,
                total_gas_spent_usd=0.0,
                total_dex_fees_usd=0.0,
                last_settlement_date=None,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(treasury)

        db.commit()

