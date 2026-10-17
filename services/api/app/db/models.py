from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import String, Integer, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BotState(Base):
    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="idle")  # idle, running, stopped, error
    mode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # PAPER, LIVE
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[str] = mapped_column(String(10))  # buy, sell
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    mode: Mapped[str] = mapped_column(String(10), default="PAPER")  # PAPER, LIVE
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, closed, cancelled
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    # Execution cost breakdown (USD) — so PnL is truly net of slippage, DEX fee and gas
    market_price: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_pct: Mapped[float] = mapped_column(Float, default=0.0)
    dex_fee_usd: Mapped[float] = mapped_column(Float, default=0.0)
    gas_fee_usd: Mapped[float] = mapped_column(Float, default=0.0)
    chain: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="Solana")
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str] = mapped_column(String(10))  # long, short
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(50), default="AI_ENGINE")
    timeframe: Mapped[str] = mapped_column(String(20), default="1h")
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, executed, expired, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_entry_price: Mapped[float] = mapped_column(Float, default=0.0)  # effective fill price (incl. slippage)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    entry_costs_usd: Mapped[float] = mapped_column(Float, default=0.0)  # DEX fee + gas paid on entry
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)  # last known pool liquidity (for exit slippage)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TreasuryState(Base):
    """Singleton: gas reserve, baseline equity for daily net-profit settlement, paper main-vault credits."""
    __tablename__ = "treasury_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gas_reserve_usd: Mapped[float] = mapped_column(Float, default=0.0)
    gas_min_idr: Mapped[float] = mapped_column(Float, default=3000.0)  # auto top-up trigger
    gas_target_idr: Mapped[float] = mapped_column(Float, default=7500.0)  # top-up up to this level
    baseline_equity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_set_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    profit_threshold_pct: Mapped[float] = mapped_column(Float, default=40.0)
    main_share_pct: Mapped[float] = mapped_column(Float, default=40.0)
    paper_main_vault_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_gas_spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_dex_fees_usd: Mapped[float] = mapped_column(Float, default=0.0)
    last_settlement_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD (WIB)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    settlement_date: Mapped[str] = mapped_column(String(10), index=True)  # WIB date
    trigger: Mapped[str] = mapped_column(String(100), default="schedule")  # schedule | manual
    status: Mapped[str] = mapped_column(String(50), default="pending")  # transferred | pending
    baseline_equity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    equity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    net_profit_usd: Mapped[float] = mapped_column(Float, default=0.0)
    net_profit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    to_main_usd: Mapped[float] = mapped_column(Float, default=0.0)
    to_capital_usd: Mapped[float] = mapped_column(Float, default=0.0)
    to_gas_usd: Mapped[float] = mapped_column(Float, default=0.0)
    main_wallet_address: Mapped[str] = mapped_column(String(100), default="")
    usd_idr: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class GasTopUp(Base):
    __tablename__ = "gas_topups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(30), default="trading_cash")  # trading_cash | settlement
    balance_after_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cash_usd: Mapped[float] = mapped_column(Float, default=0.0)
    holdings_net_usd: Mapped[float] = mapped_column(Float, default=0.0)
    gas_reserve_usd: Mapped[float] = mapped_column(Float, default=0.0)
    usd_idr: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(30), default="tick")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(100), default="")
    chain: Mapped[str] = mapped_column(String(50), default="Ethereum")
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    token: Mapped[str] = mapped_column(String(20), default="USDT")
    gate: Mapped[str] = mapped_column(String(20), default="main")  # main, trading, reserve
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIAgent(Base):
    __tablename__ = "ai_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    agent_type: Mapped[str] = mapped_column(String(30), default="analyst")  # analyst, risk, signal
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, inactive
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class RiskConfig(Base):
    __tablename__ = "risk_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    max_position_size_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, default=3.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=10.0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=2.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=10)
    allowed_symbols: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class GoldHolding(Base):
    __tablename__ = "gold_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(80), default="Emas Antam CertiEye")
    brand: Mapped[str] = mapped_column(String(40), default="Antam")  # Antam, UBS, Galeri24, Digital
    weight_grams: Mapped[float] = mapped_column(Float, default=1.0)
    buy_price_per_gram_idr: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_idr: Mapped[float] = mapped_column(Float, default=0.0)
    purchased_at: Mapped[str] = mapped_column(String(20), default="")  # YYYY-MM-DD
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class StockPortfolioPosition(Base):
    """Manual IDX Stock Portfolio position for tracking lots, avg price, sector concentration & dividend income."""
    __tablename__ = "stock_portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)  # e.g. BBRI, BBCA
    name: Mapped[str] = mapped_column(String(120), default="")
    sector: Mapped[str] = mapped_column(String(80), default="Perbankan")
    lots: Mapped[int] = mapped_column(Integer, default=1)  # 1 lot = 100 shares
    avg_buy_price: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl_idr: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class StockWatchlistItem(Base):
    """IDX Stock Watchlist & price alert levels."""
    __tablename__ = "stock_watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    target_entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_tp_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class StockSignalJournal(Base):
    """Audit journal of generated IDX stock trading plan signals for historical evaluation."""
    __tablename__ = "stock_signal_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(15), default="1d")
    strategy: Mapped[str] = mapped_column(String(60), default="Swing Trading")
    signal_direction: Mapped[str] = mapped_column(String(20), default="BUY")  # BUY, HOLD, SELL/REDUCE, WAIT
    price_at_signal: Mapped[float] = mapped_column(Float, default=0.0)
    entry_low: Mapped[float] = mapped_column(Float, default=0.0)
    entry_high: Mapped[float] = mapped_column(Float, default=0.0)
    tp_1: Mapped[float] = mapped_column(Float, default=0.0)
    tp_2: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)
    rr_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, HIT_TP1, HIT_TP2, HIT_SL, EXPIRED
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


