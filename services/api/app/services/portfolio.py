from datetime import datetime, timezone
from sqlalchemy import select, delete, or_, func, case
from sqlalchemy.orm import Session
from app.db.models import PortfolioHolding, Wallet, Trade, EquitySnapshot, TreasuryState
from app.services import market, treasury

PAPER_INITIAL_CAPITAL_IDR = 150000.0
PAPER_WALLET_NAME = "Modal Paper Simulasi (Rp 150.000)"


def get_paper_initial_capital_idr() -> float:
    try:
        from app.services import bot
        val = bot._SNIPER_CONFIG.get("paper_initial_capital_idr")
        if val is not None and float(val) > 0:
            return float(val)
    except Exception:
        pass
    return PAPER_INITIAL_CAPITAL_IDR


def set_paper_initial_capital_idr(amount_idr: float) -> float:
    val = float(amount_idr)
    if val <= 0:
        raise ValueError("Nominal modal awal harus lebih besar dari 0")
    try:
        from app.services import bot
        bot.update_sniper_config({"paper_initial_capital_idr": val}, allow_while_running=True)
    except Exception:
        pass
    return val


def get_or_create_paper_wallet(db: Session) -> tuple[Wallet, float]:
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    configured_idr = get_paper_initial_capital_idr()
    rows = db.execute(
        select(Wallet).where(
            or_(
                Wallet.name.contains("Modal Paper"),
                Wallet.address.contains("SIMULATION-PAPER"),
            )
        )
    ).scalars().all()
    if len(rows) > 1:
        for extra in rows[1:]:
            db.delete(extra)
        db.commit()
    w = rows[0] if rows else None
    if not w:
        initial_usd = round(configured_idr / usd_idr, 4)
        w = Wallet(
            name=f"Modal Paper Simulasi (Rp {configured_idr:,.0f})",
            address="SIMULATION-PAPER-WALLET",
            chain="Solana",
            balance=initial_usd,
            token="USD (Paper Simulasi)",
            gate="trading",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(w)
        db.commit()
        db.refresh(w)
    treasury.get_or_init_treasury(db, usd_idr)
    return w, usd_idr


def reset_paper_account(
    db: Session,
    initial_capital_usd: float | None = None,
    initial_capital_idr: float | None = None,
) -> dict:
    """Reset paper trading simulation to custom (or default) initial capital and clear all simulated holdings/trades."""
    from app.services import bot

    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    if initial_capital_usd is not None and float(initial_capital_usd) > 0:
        initial_usd = round(float(initial_capital_usd), 4)
        initial_idr = round(initial_usd * usd_idr, 0)
        set_paper_initial_capital_idr(initial_idr)
    elif initial_capital_idr is not None and float(initial_capital_idr) > 0:
        initial_idr = round(float(initial_capital_idr), 0)
        initial_usd = round(initial_idr / usd_idr, 4)
        set_paper_initial_capital_idr(initial_idr)
    else:
        initial_idr = get_paper_initial_capital_idr()
        initial_usd = round(initial_idr / usd_idr, 4)

    # CRITICAL: Isolate modes. Only wipe PAPER holdings, NEVER delete live on-chain positions!
    db.execute(delete(PortfolioHolding).where(PortfolioHolding.mode == "PAPER"))
    db.execute(delete(Trade).where(Trade.mode == "PAPER"))

    rows = db.execute(
        select(Wallet).where(
            or_(
                Wallet.name.contains("Modal Paper"),
                Wallet.address.contains("SIMULATION-PAPER"),
            )
        )
    ).scalars().all()
    if len(rows) > 1:
        for extra in rows[1:]:
            db.delete(extra)
    w = rows[0] if rows else None

    wallet_name = f"Modal Paper Simulasi (${initial_usd:,.2f} / Rp {initial_idr:,.0f})"
    if not w:
        w = Wallet(
            name=wallet_name,
            address="SIMULATION-PAPER-WALLET",
            chain="Solana",
            balance=initial_usd,
            token="USD (Paper Simulasi)",
            gate="trading",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(w)
    else:
        w.name = wallet_name
        w.balance = initial_usd
        w.token = "USD (Paper Simulasi)"
        w.updated_at = datetime.now(timezone.utc)

    db.commit()
    treasury.reset_treasury_for_paper(db, usd_idr, baseline_usd=initial_usd)
    bot.clear_bot_logs()
    bot._append_log(
        "SYSTEM",
        "SOL",
        "RESET",
        f"Simulasi Paper direset. Modal awal baru: ${initial_usd:,.2f} (≈ Rp {initial_idr:,.0f}).",
        f"Rp {initial_idr:,.0f}",
        "success",
    )
    return get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)

def sync_onchain_holdings_to_portfolio(db: Session) -> list[PortfolioHolding]:
    """
    Synchronize actual on-chain SPL tokens from the Live Trading Wallet into PortfolioHolding.
    Detects genuine meme coin positions held on-chain (e.g. Kimchi, LARRY, zonki),
    updates their live prices and quantities, and removes any positions whose on-chain balance is 0.
    Excludes stablecoins (USDC) and zero-liquidity/flagged spam tokens (< $50 liq).
    """
    from app.services import live_engine

    live_w, _, _ = live_engine.get_live_trading_wallet(db, "Solana")
    if not live_w or not live_w.address or live_w.address.startswith("SIMULATION"):
        return list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "LIVE")).scalars().all())

    onchain_tokens = live_engine.query_solana_spl_tokens(live_w.address, max_cache_seconds=20.0)
    if not onchain_tokens:
        return list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "LIVE")).scalars().all())
    seen_symbols = set()
    now = datetime.now(timezone.utc)
    is_fresh_rpc = live_engine.is_spl_cache_fresh(live_w.address)

    # 1. Filter eligible non-USDC meme tokens with real tradable liquidity (>= $50.0)
    valid_tokens = []
    for tok in onchain_tokens:
        mint = tok.get("mint", "")
        amt = float(tok.get("amount", 0.0))
        if mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" or amt <= 0.0001:
            continue
        liq = float(tok.get("liquidity", 0.0))
        usd_val = float(tok.get("usd_val", 0.0))
        if liq < 50.0 or usd_val <= 0.0001:
            continue
        sym = tok.get("symbol") or mint[:6]
        seen_symbols.add(sym.upper())
        valid_tokens.append(tok)

    # 2. Delete any LIVE DB holdings that are no longer present on-chain, ONLY when RPC response is 100% fresh
    if is_fresh_rpc:
        existing_live = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "LIVE")).scalars().all())
        for h in existing_live:
            if h.symbol.upper() not in seen_symbols:
                upd_dt = h.updated_at if (h.updated_at and h.updated_at.tzinfo) else (h.updated_at.replace(tzinfo=timezone.utc) if h.updated_at else None)
                if upd_dt and (now - upd_dt).total_seconds() < 60.0:
                    continue
                db.delete(h)
        db.commit()

    # 3. Upsert active on-chain holdings into PortfolioHolding with mode="LIVE"
    for tok in valid_tokens:
        sym = tok.get("symbol") or tok.get("mint", "")[:6]
        amt = float(tok.get("amount", 0.0))
        live_price = float(tok.get("price", 0.0))
        if live_price <= 0 and amt > 0 and tok.get("usd_val", 0.0) > 0:
            live_price = float(tok["usd_val"]) / amt
        liq = float(tok.get("liquidity", 1800.0))

        existing = db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.symbol == sym,
                PortfolioHolding.mode == "LIVE",
            )
        ).scalar_one_or_none()
        if existing:
            existing.quantity = amt
            if live_price > 0:
                existing.current_price = live_price
            if liq > 0:
                existing.liquidity_usd = liq
            existing.updated_at = now
        else:
            base_sym = sym.split("/")[0]
            recent_buy = (
                db.execute(
                    select(Trade)
                    .where(Trade.symbol.ilike(f"%{base_sym}%"), Trade.side == "buy", Trade.mode == "LIVE")
                    .order_by(Trade.id.desc())
                    .limit(1)
                )
                .scalar_one_or_none()
            )
            entry_px = float(recent_buy.price) if recent_buy and recent_buy.price > 0 else (live_price or 0.00001)

            new_h = PortfolioHolding(
                symbol=sym,
                mode="LIVE",
                quantity=amt,
                avg_entry_price=entry_px,
                current_price=live_price or entry_px,
                entry_costs_usd=0.001,
                liquidity_usd=liq or 1800.0,
                updated_at=now,
            )
            db.add(new_h)
        db.commit()

    return list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "LIVE")).scalars().all())


def get_overview(
    db: Session,
    refresh_live_prices: bool = True,
    mode: str | None = None,
    skip_rpc: bool | None = None,
) -> dict:
    paper_wallet, usd_idr = get_or_create_paper_wallet(db)
    t_state = treasury.get_or_init_treasury(db, usd_idr)

    active_mode = (mode or "PAPER").upper()
    is_live = active_mode == "LIVE"

    if skip_rpc is None:
        skip_rpc = not is_live

    if is_live:
        # In LIVE mode, holdings are the real on-chain SPL tokens from Phantom Trading Wallet
        live_holdings = sync_onchain_holdings_to_portfolio(db)
        holdings = live_holdings
        refresh_live_prices = False
    else:
        # In PAPER mode, holdings are simulated paper holdings from PortfolioHolding (strictly PAPER)
        holdings = db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "PAPER")).scalars().all()
    total_value = 0.0
    total_net_value = 0.0
    total_cost = 0.0
    total_net_pnl = 0.0
    items = []
    dirty = False

    for h in holdings:
        if refresh_live_prices:
            live_tok = market.get_live_token_info(h.symbol)
            if live_tok and live_tok.get("price", 0) > 0:
                h.current_price = float(live_tok["price"])
                if live_tok.get("liquidity", 0) > 0:
                    h.liquidity_usd = float(live_tok["liquidity"])
                h.updated_at = datetime.now(timezone.utc)
                dirty = True

        net_m = treasury.compute_holding_net_metrics(h, usd_idr)
        value = net_m["gross_value_usd"]
        net_val = net_m["net_value_usd"]
        cost = net_m["cost_usd"]
        pnl = net_m["net_pnl_usd"]  # Net PnL after entry & exit slippage, DEX fees, and gas
        pnl_pct = net_m["net_pnl_pct"]

        total_value += value
        total_net_value += net_val
        total_cost += cost
        total_net_pnl += pnl

        items.append({
            "id": h.id,
            "symbol": h.symbol,
            "quantity": h.quantity,
            "avg_entry_price": h.avg_entry_price,
            "avg_entry_price_idr": round(h.avg_entry_price * usd_idr, 2),
            "current_price": h.current_price,
            "current_price_idr": round(h.current_price * usd_idr, 2),
            "value": round(value, 4),
            "value_idr": round(value * usd_idr, 0),
            "net_value_usd": round(net_val, 4),
            "net_value_idr": round(net_val * usd_idr, 0),
            "cost": round(cost, 4),
            "cost_idr": round(cost * usd_idr, 0),
            "pnl": round(pnl, 4),
            "pnl_idr": round(pnl * usd_idr, 0),
            "pnl_pct": round(pnl_pct, 2),
            "gross_pnl_pct": net_m["gross_pnl_pct"],
            "est_exit_cost_idr": net_m["est_exit_cost_idr"],
            "exit_slippage_pct": net_m["exit_slippage_pct"],
            "updated_at": h.updated_at.isoformat() if h.updated_at else None,
        })

    if dirty:
        db.commit()

    unrealized_pnl = total_net_pnl
    unrealized_pnl_pct = (unrealized_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
    paper_cash_usd = float(paper_wallet.balance)
    paper_cash_idr = round(paper_cash_usd * usd_idr, 0)
    initial_capital_usd = float(t_state.baseline_equity_usd or round(get_paper_initial_capital_idr() / usd_idr, 4))
    initial_capital_idr = round(initial_capital_usd * usd_idr, 0)
    total_equity_usd = paper_cash_usd + total_net_value
    total_equity_idr = round(total_equity_usd * usd_idr, 0)

    # Record a live EquitySnapshot if holdings exist and prices were refreshed
    if refresh_live_prices and len(items) > 0:
        last_snap = (
            db.execute(select(EquitySnapshot).order_by(EquitySnapshot.id.desc()).limit(1))
            .scalar_one_or_none()
        )
        should_snap = False
        if not last_snap:
            should_snap = True
        else:
            last_dt = last_snap.created_at
            if last_dt and last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() if last_dt else 999
            if elapsed >= 5.0 or abs(float(last_snap.equity_usd) - total_equity_usd) >= 0.0005:
                should_snap = True
        if should_snap:
            treasury.record_equity_snapshot(
                db,
                equity_usd=total_equity_usd,
                cash_usd=paper_cash_usd,
                holdings_net_usd=total_net_value,
                gas_reserve_usd=t_state.gas_reserve_usd,
                usd_idr=usd_idr,
                reason="live_market_tick",
            )

    from app.services import live_engine
    live_eq = live_engine.get_live_equity_metrics(db, usd_idr, skip_rpc=skip_rpc)

    active_mode = (mode or "PAPER").upper()
    is_live = active_mode == "LIVE"
    active_total_equity_usd = live_eq["live_total_equity_usd"] if is_live else total_equity_usd
    active_total_equity_idr = round(active_total_equity_usd * usd_idr, 0)
    active_cash_usd = live_eq["live_cash_usd"] if is_live else paper_cash_usd
    active_cash_idr = round(active_cash_usd * usd_idr, 0)

    # 1 SQL aggregate query for winrate stats
    try:
        stmt = (
            select(
                func.count(Trade.id).label("total_trades"),
                func.coalesce(func.sum(case((Trade.pnl > 0, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((Trade.pnl <= 0, 1), else_=0)), 0).label("losses"),
                func.coalesce(func.sum(Trade.pnl), 0.0).label("realized_usd"),
            )
            .where(Trade.side == "sell", Trade.status == "closed", Trade.mode == active_mode)
        )
        row = db.execute(stmt).first()
        if row:
            alltime_total = int(row.total_trades or 0)
            alltime_wins = int(row.wins or 0)
            alltime_losses = int(row.losses or 0)
            alltime_realized_usd = float(row.realized_usd or 0.0)
        else:
            alltime_total = alltime_wins = alltime_losses = 0
            alltime_realized_usd = 0.0
    except Exception:
        alltime_total = alltime_wins = alltime_losses = 0
        alltime_realized_usd = 0.0

    alltime_winrate_pct = round((alltime_wins / alltime_total) * 100.0, 1) if alltime_total > 0 else 0.0

    return {
        "usd_idr": usd_idr,
        "active_mode": active_mode,
        "is_live": is_live,
        "active_total_equity_usd": round(active_total_equity_usd, 4),
        "active_total_equity_idr": active_total_equity_idr,
        "active_cash_usd": round(active_cash_usd, 4),
        "active_cash_idr": active_cash_idr,
        "paper_initial_idr": round(initial_capital_idr, 0),
        "paper_initial_usd": round(initial_capital_usd, 4),
        "paper_cash_usd": round(paper_cash_usd, 4),
        "paper_cash_idr": paper_cash_idr,
        "live_cash_usd": live_eq["live_cash_usd"],
        "live_cash_idr": live_eq["live_cash_idr"],
        "live_holdings_usd": live_eq.get("live_holdings_usd", round(total_net_value, 2)),
        "live_holdings_idr": live_eq.get("live_holdings_idr", round(total_net_value * usd_idr, 0)),
        "live_usdc_usd": live_eq.get("live_usdc_usd", 0.0),
        "live_usdc_idr": live_eq.get("live_usdc_idr", 0.0),
        "live_gas_sol": live_eq.get("live_gas_sol", 0.0),
        "live_gas_usd": live_eq.get("live_gas_usd", 0.0),
        "live_gas_idr": live_eq.get("live_gas_idr", 0.0),
        "live_total_equity_usd": round(live_eq["live_total_equity_usd"], 2),
        "live_total_equity_idr": round(live_eq["live_total_equity_usd"] * usd_idr, 0),
        "gas_reserve_usd": round(t_state.gas_reserve_usd, 4),
        "gas_reserve_idr": round(t_state.gas_reserve_usd * usd_idr, 0),
        "total_gas_spent_idr": round((t_state.total_gas_spent_usd or 0.0) * usd_idr, 0),
        "total_dex_fees_idr": round((t_state.total_dex_fees_usd or 0.0) * usd_idr, 0),
        "total_equity_usd": round(active_total_equity_usd if is_live else total_equity_usd, 4),
        "total_equity_idr": active_total_equity_idr if is_live else total_equity_idr,
        "total_value": round(total_value, 4),
        "total_value_idr": round(total_value * usd_idr, 0),
        "net_holdings_value_usd": round(total_net_value, 4),
        "net_holdings_value_idr": round(total_net_value * usd_idr, 0),
        "total_cost": round(total_cost, 4),
        "total_cost_idr": round(total_cost * usd_idr, 0),
        "unrealized_pnl": round(unrealized_pnl, 4),
        "unrealized_pnl_idr": round(unrealized_pnl * usd_idr, 0),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        "alltime_winrate_pct": alltime_winrate_pct,
        "alltime_wins": alltime_wins,
        "alltime_losses": alltime_losses,
        "alltime_trades": alltime_total,
        "alltime_realized_pnl_usd": round(alltime_realized_usd, 4),
        "alltime_realized_pnl_idr": round(alltime_realized_usd * usd_idr, 0),
        "holdings": items,
    }


def add_holding(
    db: Session,
    symbol: str,
    quantity: float,
    avg_entry_price: float,
    current_price: float | None = None,
    entry_costs_usd: float = 0.0,
    liquidity_usd: float = 25000.0,
    mode: str = "PAPER",
) -> PortfolioHolding:
    existing = db.execute(
        select(PortfolioHolding).where(
            PortfolioHolding.symbol == symbol,
            PortfolioHolding.mode == mode,
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        total_qty = existing.quantity + quantity
        if total_qty > 0:
            existing.avg_entry_price = (existing.quantity * existing.avg_entry_price + quantity * avg_entry_price) / total_qty
        existing.quantity = total_qty
        existing.entry_costs_usd = float(existing.entry_costs_usd or 0.0) + float(entry_costs_usd or 0.0)
        if liquidity_usd > 0:
            existing.liquidity_usd = liquidity_usd
        if current_price is not None:
            existing.current_price = current_price
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    holding = PortfolioHolding(
        symbol=symbol,
        mode=mode,
        quantity=quantity,
        avg_entry_price=avg_entry_price,
        current_price=current_price if current_price is not None else avg_entry_price,
        entry_costs_usd=float(entry_costs_usd or 0.0),
        liquidity_usd=float(liquidity_usd or 25000.0),
        updated_at=now,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def sell_holding(db: Session, symbol: str, sell_pct: float = 100.0, mode: str | None = None) -> dict:
    """
    Sell a percentage (e.g. 25, 50, 100) of a holding at the 100% real live DexScreener market price,
    deducting real exit slippage, DEX swap fee (0.25%), and network gas fee.
    Supports both PAPER mode and LIVE mode (crediting the Live Trading Hot Wallet & Neonbase Journal).
    """
    from app.services import live_engine

    clean_sym = str(symbol or "").strip()
    q = select(PortfolioHolding).where(
        or_(
            PortfolioHolding.symbol == clean_sym,
            func.upper(PortfolioHolding.symbol) == clean_sym.upper(),
        )
    )
    if mode:
        q = q.where(PortfolioHolding.mode == mode.upper())
    existing = db.execute(q).scalars().first()
    if not existing or existing.quantity <= 0:
        raise ValueError(f"Holding {clean_sym} tidak ditemukan di portofolio.")

    # Check original buy trade mode
    open_buy = db.execute(
        select(Trade).where(Trade.symbol == symbol, Trade.side == "buy").order_by(Trade.id.desc()).limit(1)
    ).scalar_one_or_none()
    trade_mode = (mode or (existing.mode if existing else None) or (open_buy.mode if open_buy else "PAPER")).upper()
    if trade_mode not in ("PAPER", "LIVE"):
        trade_mode = "PAPER"

    paper_wallet, usd_idr = get_or_create_paper_wallet(db)

    # Fetch 100% real live price from DexScreener
    live_tok = market.get_live_token_info(symbol)
    resolved_price = float(live_tok["price"]) if (live_tok and live_tok.get("price", 0) > 0) else float(existing.current_price)
    # Sanity guard: if resolved_price is over 50x higher than entry price due to cross-chain ticker collision, protect from inflated price
    if existing.avg_entry_price > 0 and resolved_price > (existing.avg_entry_price * 50.0):
        if existing.current_price > 0 and existing.current_price < (existing.avg_entry_price * 5.0):
            resolved_price = float(existing.current_price)
    market_price = resolved_price
    liq_usd = float(live_tok["liquidity"]) if (live_tok and live_tok.get("liquidity", 0) > 0) else float(existing.liquidity_usd or 25000.0)
    tok_ca = str((live_tok.get("contract") if live_tok else "") or "")
    target_chain = "Solana" if (trade_mode == "LIVE" or not tok_ca.startswith("0x")) else "Base"

    pct = max(1.0, min(100.0, float(sell_pct))) / 100.0
    qty_to_sell = existing.quantity * pct
    gross_proceeds_usd = qty_to_sell * market_price

    try:
        from app.services import bot as bot_svc
        cfg_slip = float(bot_svc._SNIPER_CONFIG.get("slippage_pct", 1.2))
        cfg_prio = float(bot_svc._SNIPER_CONFIG.get("priority_fee_sol", 0.0008))
        active_strat_tag = str(bot_svc._SNIPER_CONFIG.get("strategy_mode", "DEFAULT")).upper()
    except Exception:
        cfg_slip = 1.2
        cfg_prio = 0.0008
        active_strat_tag = "DEFAULT"

    # Calculate exit slippage, DEX fee, and gas fee
    exec_costs = treasury.compute_execution_costs(
        notional_usd=gross_proceeds_usd,
        liquidity_usd=liq_usd,
        user_slippage_pct=cfg_slip,
        priority_fee_sol=cfg_prio,
    )
    exit_slippage_pct = exec_costs["effective_slippage_pct"]
    sell_fill_price = market_price * (1.0 - exit_slippage_pct / 100.0)
    after_slippage_usd = qty_to_sell * sell_fill_price
    dex_fee_usd = round(after_slippage_usd * (exec_costs["dex_fee_pct"] / 100.0), 6)
    gas_fee_usd = exec_costs["gas_fee_usd"]
    net_proceeds_usd = max(0.0, after_slippage_usd - dex_fee_usd)

    cost_basis_usd = qty_to_sell * existing.avg_entry_price
    prop_entry_gas_usd = float(existing.entry_costs_usd or 0.0) * pct
    # Net Realized PnL accounts for entry slippage + entry DEX fee + entry gas + exit slippage + exit DEX fee + exit gas
    realized_pnl_usd = net_proceeds_usd - cost_basis_usd - prop_entry_gas_usd - gas_fee_usd

    t_state = treasury.get_or_init_treasury(db, usd_idr)
    tx_hash = ""

    if trade_mode == "LIVE":
        live_wallet, _, _ = live_engine.get_live_trading_wallet(db, target_chain, create_if_missing=False)
        if not live_wallet:
            raise ValueError("LIVE_WALLET_NOT_FOUND: Wallet trading live tidak ditemukan.")

        # Pre-Flight Gas Check for Sell: Pastikan wallet memiliki sedikit SOL untuk biaya gas transaksi jual
        current_sol_bal = float(live_wallet.balance or 0.0)
        if current_sol_bal < 0.0005:
            raise ValueError(
                f"GAS_SOL_HABIS: Saldo SOL wallet ({current_sol_bal:.6f} SOL) tidak cukup untuk membayar gas fee transaksi jual di Solana. "
                f"Minimal butuh 0.001 SOL agar transaksi jual tidak gantung."
            )

        token_info = market.get_live_token_info(symbol)
        token_contract = (token_info.get("contract") if token_info else None) or getattr(existing, "contract", None)

        from app.services import solana_trader
        kp = solana_trader.get_trading_keypair()
        kp_pubkey = str(kp.pubkey()) if kp else ""
        is_real_onchain = (
            bool(kp)
            and bool(live_wallet.address)
            and live_wallet.address == kp_pubkey
            and not live_wallet.address.startswith("11111111111111111111111111111111")
        )

        if not is_real_onchain:
            raise ValueError(
                "KEYPAIR_LIVE_TIDAK_COCOK: Private Key wallet trading tidak cocok dengan alamat wallet live yang aktif. "
                "Eksekusi dummy dinonaktifkan (100% Real On-Chain Mode)."
            )

        # Pre-Flight Token Existence Check: Pastikan token benar-benar ada di wallet on-chain
        spl_tokens = live_engine.query_solana_spl_tokens(live_wallet.address, max_cache_seconds=10.0)
        base_sym_upper = symbol.split("/")[0].upper()
        token_entry = next(
            (
                t for t in spl_tokens
                if (token_contract and t.get("mint") == token_contract)
                or (t.get("symbol") or "").upper() == symbol.upper()
                or (t.get("symbol") or "").split("/")[0].upper() == base_sym_upper
            ),
            None,
        )

        if not token_entry or float(token_entry.get("amount") or 0.0) <= 0:
            # Hanya bersihkan sebagai orphan jika data RPC benar-benar fresh (bukan fallback 429)
            if live_engine.is_spl_cache_fresh(live_wallet.address):
                db.delete(existing)
                if open_buy and open_buy.status == "open":
                    open_buy.status = "closed"
                    open_buy.result = "ORPHAN_CLEARED"
                    open_buy.closed_at = datetime.now(timezone.utc)
                    open_buy.notes = f"Posisi {symbol} dibersihkan karena token tidak ditemukan di wallet on-chain."
                db.commit()
            return {
                "symbol": symbol,
                "status": "cleared",
                "message": f"Posisi {symbol} belum ditemukan atau saldo on-chain 0.",
                "sell_price_usd": market_price,
                "realized_pnl_usd": 0.0,
                "realized_pnl_idr": 0.0,
                "slippage_pct": 0.0,
                "dex_fee_idr": 0.0,
                "gas_fee_idr": 0.0,
                "cash_remaining_idr": round(float(live_wallet.balance or 0.0) * live_engine.get_sol_price_usd() * usd_idr),
            }

        # Gunakan kontrak mint asli & harga asli dari token on-chain di wallet (menghindari ticker collision)
        token_contract = token_entry.get("mint") or token_contract
        if float(token_entry.get("price") or 0.0) > 0:
            market_price = float(token_entry["price"])
            gross_proceeds_usd = qty_to_sell * market_price
            sell_fill_price = market_price * (1.0 - exit_slippage_pct / 100.0)
            after_slippage_usd = qty_to_sell * sell_fill_price
            dex_fee_usd = round(after_slippage_usd * (exec_costs["dex_fee_pct"] / 100.0), 6)
            net_proceeds_usd = max(0.0, after_slippage_usd - dex_fee_usd)
            realized_pnl_usd = net_proceeds_usd - cost_basis_usd - prop_entry_gas_usd - gas_fee_usd

        total_raw = int(token_entry.get("amount_raw") or round(qty_to_sell * (10 ** int(token_entry.get("decimals", 6)))))
        raw_units = max(1, int(round(total_raw * pct)))
        onchain_tx_res = solana_trader.execute_onchain_token_to_sol(
            token_mint=token_contract,
            amount_tokens_raw=raw_units,
            slippage_pct=max(exit_slippage_pct, cfg_slip),
        )
        if not onchain_tx_res or not onchain_tx_res.get("tx_hash"):
            raise RuntimeError("Transaksi jual on-chain gagal: tidak menerima signature transaksi yang valid.")
        tx_hash = onchain_tx_res["tx_hash"]
        live_engine.remove_spl_cache_token(
            live_wallet.address,
            symbol,
            sell_pct=float(sell_pct),
            mint=token_contract,
        )

        net_credit_usd = max(0.0, net_proceeds_usd - gas_fee_usd)
        remaining_cash_usd = live_engine.credit_live_wallet_usd(db, live_wallet, net_credit_usd)
        wallet_label = live_wallet.name
        try:
            from app.services import wallets as wallet_svc
            wallet_svc.sync_wallet_onchain(db, live_wallet.id, apply_onchain_balance=True)
        except Exception:
            pass
        t_state.total_gas_spent_usd = float(t_state.total_gas_spent_usd or 0.0) + gas_fee_usd
        t_state.total_dex_fees_usd = float(t_state.total_dex_fees_usd or 0.0) + dex_fee_usd
    else:
        tx_hash = live_engine.generate_tx_hash(target_chain)
        # Charge gas fee from Gas Reserve (auto-topping up if reserve < Rp 3.000)
        t_state = treasury.charge_gas_and_dex_fee(
            db,
            paper_wallet=paper_wallet,
            usd_idr=usd_idr,
            gas_fee_usd=gas_fee_usd,
            dex_fee_usd=dex_fee_usd,
        )
        # Credit net proceeds back to Paper Wallet
        paper_wallet.balance = float(paper_wallet.balance) + net_proceeds_usd
        paper_wallet.updated_at = datetime.now(timezone.utc)
        remaining_cash_usd = float(paper_wallet.balance)
        wallet_label = paper_wallet.name

    # If closing 100% of an open buy trade, remove the open placeholder so the closed trade record is clean
    opened_time = existing.updated_at or datetime.now(timezone.utc)
    if open_buy and open_buy.status == "open":
        opened_time = open_buy.opened_at or opened_time
        if pct >= 0.999:
            db.delete(open_buy)

    # Record closed trade with full fee breakdown
    trade = Trade(
        symbol=symbol,
        side="sell",
        quantity=qty_to_sell,
        price=sell_fill_price,
        total=net_proceeds_usd,
        mode=trade_mode,
        status="closed",
        pnl=round(realized_pnl_usd, 6),
        market_price=market_price,
        slippage_pct=exit_slippage_pct,
        dex_fee_usd=dex_fee_usd,
        gas_fee_usd=gas_fee_usd,
        chain=target_chain,
        tx_hash=tx_hash,
        notes=f"[{active_strat_tag}] {'Live On-Chain Sell' if trade_mode == 'LIVE' else 'Paper Sell'} ({sell_pct:.0f}%) via {wallet_label}",
        opened_at=opened_time,
        closed_at=datetime.now(timezone.utc),
    )
    db.add(trade)

    if pct >= 0.999:
        db.delete(existing)
    else:
        existing.quantity = existing.quantity - qty_to_sell
        existing.entry_costs_usd = max(0.0, float(existing.entry_costs_usd or 0.0) - prop_entry_gas_usd)
        existing.current_price = market_price
        existing.updated_at = datetime.now(timezone.utc)

    db.commit()

    # Record equity snapshot after sell
    ov = get_overview(db, refresh_live_prices=False)
    treasury.record_equity_snapshot(
        db,
        equity_usd=float(ov["total_equity_usd"]),
        cash_usd=float(ov["paper_cash_usd"]),
        holdings_net_usd=float(ov.get("net_holdings_value_usd", 0.0)),
        gas_reserve_usd=t_state.gas_reserve_usd,
        usd_idr=usd_idr,
        reason=f"sell:{trade_mode}:{symbol}",
    )

    return {
        "status": "sold",
        "mode": trade_mode,
        "symbol": symbol,
        "chain": target_chain,
        "tx_hash": tx_hash,
        "wallet_name": wallet_label,
        "qty_sold": round(qty_to_sell, 4),
        "market_price_usd": market_price,
        "sell_price_usd": round(sell_fill_price, 8),
        "sell_price_idr": round(sell_fill_price * usd_idr, 2),
        "slippage_pct": exit_slippage_pct,
        "dex_fee_usd": round(dex_fee_usd, 6),
        "dex_fee_idr": round(dex_fee_usd * usd_idr, 0),
        "gas_fee_usd": round(gas_fee_usd, 6),
        "gas_fee_idr": round(gas_fee_usd * usd_idr, 0),
        "proceeds_usd": round(net_proceeds_usd, 4),
        "proceeds_idr": round(net_proceeds_usd * usd_idr, 0),
        "realized_pnl_usd": round(realized_pnl_usd, 4),
        "realized_pnl_idr": round(realized_pnl_usd * usd_idr, 0),
        "cash_remaining_usd": round(remaining_cash_usd, 4),
        "cash_remaining_idr": round(remaining_cash_usd * usd_idr, 0),
        "paper_cash_usd": round(paper_wallet.balance, 4),
        "paper_cash_idr": round(paper_wallet.balance * usd_idr, 0),
        "gas_reserve_idr": round(t_state.gas_reserve_usd * usd_idr, 0),
    }


def sell_all_holdings(db: Session, mode: str | None = None) -> dict:
    """Emergency / Panic Sell 100% of all open holdings at live market prices."""
    active_mode = (mode or "PAPER").upper()
    q = select(PortfolioHolding).where(PortfolioHolding.mode == active_mode)
    holdings = list(db.execute(q).scalars().all())
    results = []
    total_proceeds_idr = 0.0
    total_pnl_idr = 0.0

    for h in holdings:
        if h.quantity > 0:
            res = sell_holding(db, h.symbol, 100.0, mode=active_mode)
            results.append(res)
            total_proceeds_idr += float(res.get("proceeds_idr") or 0.0)
            total_pnl_idr += float(res.get("realized_pnl_idr") or 0.0)

    return {
        "status": "liquidated_all",
        "positions_closed": len(results),
        "total_proceeds_idr": round(total_proceeds_idr, 0),
        "total_realized_pnl_idr": round(total_pnl_idr, 0),
        "results": results,
    }


def update_price(db: Session, symbol: str, price: float, mode: str = "PAPER") -> PortfolioHolding:
    existing = db.execute(
        select(PortfolioHolding).where(
            PortfolioHolding.symbol == symbol,
            PortfolioHolding.mode == mode,
        )
    ).scalar_one_or_none()
    if not existing:
        raise ValueError(f"Holding {symbol} not found")
    existing.current_price = price
    existing.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(existing)
    return existing

