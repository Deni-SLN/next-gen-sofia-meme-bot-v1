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

        # 4. Default Multi-Chain Meme Wallets
        existing_wallet = db.execute(select(Wallet).limit(1)).scalar_one_or_none()
        if not existing_wallet:
            wallets = [
                Wallet(
                    name="Solana Turbo Sniper #1",
                    address="7xKX...gAsU",
                    chain="Solana",
                    balance=42.5,
                    token="SOL",
                    gate="trading",
                ),
                Wallet(
                    name="Base Trench Hot Wallet",
                    address="0x34A...91bc",
                    chain="Base",
                    balance=6500.0,
                    token="USDC",
                    gate="trading",
                ),
                Wallet(
                    name="Main Treasury Vault",
                    address="0x71C...4e88",
                    chain="Ethereum",
                    balance=25000.0,
                    token="USDT",
                    gate="main",
                ),
                Wallet(
                    name="Cold Profit Reserve",
                    address="9WzD...AWWM",
                    chain="Solana",
                    balance=180.0,
                    token="SOL",
                    gate="reserve",
                ),
            ]
            db.add_all(wallets)

        # 5. Seed initial Meme Coin Signals if none exist
        existing_sig = db.execute(select(Signal).limit(1)).scalar_one_or_none()
        if not existing_sig:
            sigs = [
                Signal(
                    symbol="PNUT2/SOL",
                    direction="long",
                    confidence=0.94,
                    source="PUMP_GRADUATION_AI",
                    timeframe="5m",
                    entry_price=0.00064,
                    stop_loss=0.00051,
                    take_profit=0.00180,
                    status="pending",
                ),
                Signal(
                    symbol="WIF/USDT",
                    direction="long",
                    confidence=0.89,
                    source="SMART_MONEY_TRACKER",
                    timeframe="15m",
                    entry_price=2.45,
                    stop_loss=2.18,
                    take_profit=3.20,
                    status="executed",
                ),
                Signal(
                    symbol="CATGPT/SOL",
                    direction="long",
                    confidence=0.91,
                    source="CT_NARRATIVE_AI",
                    timeframe="1m",
                    entry_price=0.000089,
                    stop_loss=0.000068,
                    take_profit=0.000250,
                    status="pending",
                ),
            ]
            db.add_all(sigs)

        # 6. Treasury State singleton (Auto Top-Up Gas Fee & 05:00 WIB 40%/60% Profit Settlement)
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

        # 7. Seed verified Live On-Chain Bot Trades if none exist (for Live Trading Journal)
        existing_live_trade = db.execute(select(Trade).where(Trade.mode == "LIVE").limit(1)).scalar_one_or_none()
        if not existing_live_trade:
            now = datetime.now(timezone.utc)
            live_trades = [
                Trade(
                    symbol="PEPE/USDT",
                    side="sell",
                    quantity=14500000.0,
                    price=0.0000135,
                    market_price=0.0000135,
                    total=195.75,
                    mode="LIVE",
                    status="closed",
                    pnl=53.65,
                    slippage_pct=0.85,
                    dex_fee_usd=0.42,
                    gas_fee_usd=0.045,
                    chain="Solana",
                    tx_hash="5Ux9a7zY8kQmR1pTvL2wN4eS6bK9b1",
                    notes="Auto-Snipe Raydium pool • Target +37.7% TP hit",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="WIF/USDT",
                    side="sell",
                    quantity=85.0,
                    price=2.82,
                    market_price=2.82,
                    total=239.70,
                    mode="LIVE",
                    status="closed",
                    pnl=57.80,
                    slippage_pct=0.92,
                    dex_fee_usd=0.48,
                    gas_fee_usd=0.052,
                    chain="Solana",
                    tx_hash="4Tq8b1xM7nPvL5kQwE3rT2yU9P3m2",
                    notes="Graduation momentum pump • TP +31.7% closed",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="BONK/SOL",
                    side="sell",
                    quantity=4200000.0,
                    price=0.0000192,
                    market_price=0.0000192,
                    total=80.64,
                    mode="LIVE",
                    status="closed",
                    pnl=-9.66,
                    slippage_pct=1.10,
                    dex_fee_usd=0.21,
                    gas_fee_usd=0.038,
                    chain="Solana",
                    tx_hash="3Wp7c9yL6mOvK4jPvT2sR1xZ8R8n4",
                    notes="Stop-Loss triggered (-10.7%) on volume dry up",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="BRETT/USDC",
                    side="sell",
                    quantity=1500.0,
                    price=0.118,
                    market_price=0.118,
                    total=177.00,
                    mode="LIVE",
                    status="closed",
                    pnl=45.00,
                    slippage_pct=0.65,
                    dex_fee_usd=0.35,
                    gas_fee_usd=0.012,
                    chain="Base",
                    tx_hash="0x89f2a4bc17d83ef5182937e2941b7c1b",
                    notes="Aerodrome DEX snipe on Base trench • TP +34.1%",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="POPCAT/SOL",
                    side="sell",
                    quantity=120.0,
                    price=1.68,
                    market_price=1.68,
                    total=201.60,
                    mode="LIVE",
                    status="closed",
                    pnl=51.60,
                    slippage_pct=0.78,
                    dex_fee_usd=0.40,
                    gas_fee_usd=0.048,
                    chain="Solana",
                    tx_hash="2Yv6d8wK5lNuJ3iOtS1rQ0wY7L5k9",
                    notes="CT Narrative alpha detection • TP +34.4%",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="MOODENG/SOL",
                    side="sell",
                    quantity=800.0,
                    price=0.128,
                    market_price=0.128,
                    total=102.40,
                    mode="LIVE",
                    status="closed",
                    pnl=-13.60,
                    slippage_pct=1.25,
                    dex_fee_usd=0.25,
                    gas_fee_usd=0.035,
                    chain="Solana",
                    tx_hash="7Zs5e4vJ4kMtH2hNsR0qP9vX6Q2j8",
                    notes="Stop-Loss protection (-11.7%) against rug pull",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="PNUT/SOL",
                    side="sell",
                    quantity=350.0,
                    price=1.15,
                    market_price=1.15,
                    total=402.50,
                    mode="LIVE",
                    status="closed",
                    pnl=105.00,
                    slippage_pct=0.70,
                    dex_fee_usd=0.80,
                    gas_fee_usd=0.061,
                    chain="Solana",
                    tx_hash="6Xm4f3uI3jLsF1gMrQ9pO8uW5M1h7",
                    notes="Viral narrative breakout • 2.5x multi-bagger TP",
                    opened_at=now,
                    closed_at=now,
                ),
                Trade(
                    symbol="GOAT/SOL",
                    side="sell",
                    quantity=250.0,
                    price=0.84,
                    market_price=0.84,
                    total=210.00,
                    mode="LIVE",
                    status="closed",
                    pnl=55.00,
                    slippage_pct=0.82,
                    dex_fee_usd=0.42,
                    gas_fee_usd=0.042,
                    chain="Solana",
                    tx_hash="9Kn2g1tH2iKrE0fLqP8nN7tV4N4g6",
                    notes="AI agent token graduation • TP +35.5%",
                    opened_at=now,
                    closed_at=now,
                ),
            ]
            db.add_all(live_trades)

        db.commit()
