from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.db.models import (
    TreasuryState,
    Settlement,
    GasTopUp,
    EquitySnapshot,
    Wallet,
    PortfolioHolding,
)
from app.services import market

WIB_TZ = timezone(timedelta(hours=7))
INITIAL_GAS_RESERVE_IDR = 5000.0
DEFAULT_GAS_MIN_IDR = 3000.0
DEFAULT_GAS_TARGET_IDR = 7500.0
DEX_LP_FEE_PCT = 0.25  # 0.25% Raydium / PumpSwap LP fee


def now_wib() -> datetime:
    return datetime.now(WIB_TZ)


def next_0500_wib_iso() -> str:
    cur = now_wib()
    target = cur.replace(hour=5, minute=0, second=0, microsecond=0)
    if cur >= target:
        target = target + timedelta(days=1)
    return target.isoformat()


def get_or_init_treasury(db: Session, usd_idr: float | None = None) -> TreasuryState:
    if usd_idr is None:
        usd_idr = market.get_fx_rate()["usd_idr"]
    t = db.execute(select(TreasuryState).where(TreasuryState.id == 1)).scalar_one_or_none()
    from app.services import portfolio as portfolio_svc
    init_cap_usd = round(portfolio_svc.get_paper_initial_capital_idr() / usd_idr, 6)
    init_gas_usd = round(INITIAL_GAS_RESERVE_IDR / usd_idr, 6)
    if not t:
        t = TreasuryState(
            id=1,
            gas_reserve_usd=init_gas_usd,
            gas_min_idr=DEFAULT_GAS_MIN_IDR,
            gas_target_idr=DEFAULT_GAS_TARGET_IDR,
            baseline_equity_usd=init_cap_usd,
            baseline_set_at=datetime.now(timezone.utc),
            profit_threshold_pct=40.0,
            main_share_pct=40.0,
            paper_main_vault_usd=0.0,
            total_gas_spent_usd=0.0,
            total_dex_fees_usd=0.0,
            last_settlement_date=None,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(t)
        db.commit()
        db.refresh(t)
    elif t.baseline_equity_usd <= 0:
        t.baseline_equity_usd = init_cap_usd
        if t.gas_reserve_usd <= 0:
            t.gas_reserve_usd = init_gas_usd
        db.commit()
        db.refresh(t)
    return t


def reset_treasury_for_paper(db: Session, usd_idr: float, baseline_usd: float | None = None) -> TreasuryState:
    """Reset treasury state when Paper Account is reset with custom or default capital."""
    from app.services import portfolio as portfolio_svc
    db.execute(delete(Settlement))
    db.execute(delete(GasTopUp))
    db.execute(delete(EquitySnapshot))
    t = get_or_init_treasury(db, usd_idr)
    configured_idr = portfolio_svc.get_paper_initial_capital_idr()
    init_usd = float(baseline_usd) if (baseline_usd is not None and float(baseline_usd) > 0) else round(configured_idr / usd_idr, 6)
    t.gas_reserve_usd = round(INITIAL_GAS_RESERVE_IDR / usd_idr, 6)
    t.gas_min_idr = DEFAULT_GAS_MIN_IDR
    t.gas_target_idr = DEFAULT_GAS_TARGET_IDR
    t.baseline_equity_usd = init_usd
    t.baseline_set_at = datetime.now(timezone.utc)
    t.profit_threshold_pct = 40.0
    t.main_share_pct = 40.0
    t.paper_main_vault_usd = 0.0
    t.total_gas_spent_usd = 0.0
    t.total_dex_fees_usd = 0.0
    t.last_settlement_date = None
    t.updated_at = datetime.now(timezone.utc)

    # Record initial snapshot at Rp 150.000
    snap = EquitySnapshot(
        equity_usd=t.baseline_equity_usd,
        cash_usd=t.baseline_equity_usd,
        holdings_net_usd=0.0,
        gas_reserve_usd=t.gas_reserve_usd,
        usd_idr=usd_idr,
        reason="reset",
        created_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    db.commit()
    db.refresh(t)
    return t


def compute_execution_costs(
    notional_usd: float,
    liquidity_usd: float = 25000.0,
    user_slippage_pct: float = 1.0,
    priority_fee_sol: float = 0.0008,
) -> dict:
    """
    Calculate realistic DEX execution costs:
    1. Effective price slippage (%) based on order size vs pool liquidity + base spread
    2. DEX LP Swap Fee (0.25% Raydium/PumpSwap standard)
    3. Network Gas + Jito Priority Fee in USD
    """
    liq = max(float(liquidity_usd or 25000.0), 2500.0)
    price_impact_pct = (notional_usd / liq) * 100.0
    base_slippage_pct = 0.30 + price_impact_pct
    max_allowed = max(0.35, min(float(user_slippage_pct or 1.0), 5.0))
    effective_slippage_pct = round(min(max_allowed, max(0.25, base_slippage_pct)), 4)

    slippage_usd = round(notional_usd * (effective_slippage_pct / 100.0), 6)
    dex_fee_usd = round(notional_usd * (DEX_LP_FEE_PCT / 100.0), 6)
    raw_gas_usd = min(0.03, max(0.002, float(priority_fee_sol or 0.0008) * 2.5))
    # Scale gas fee proportionally on micro-trades so small positions ($0.10 - $2.00) do not start at -10% net PnL
    gas_fee_usd = round(min(raw_gas_usd, max(0.0004, notional_usd * 0.003)) if notional_usd > 0 else raw_gas_usd, 6)

    return {
        "effective_slippage_pct": effective_slippage_pct,
        "slippage_usd": slippage_usd,
        "dex_fee_pct": DEX_LP_FEE_PCT,
        "dex_fee_usd": dex_fee_usd,
        "gas_fee_usd": gas_fee_usd,
        "total_cost_usd": round(slippage_usd + dex_fee_usd + gas_fee_usd, 6),
    }


def ensure_gas_reserve(
    db: Session,
    paper_wallet: Wallet,
    usd_idr: float,
    needed_gas_usd: float = 0.0,
    force_topup_idr: float | None = None,
) -> dict:
    """
    Auto Top-Up Gas Fee:
    Whenever gas_reserve_idr falls below gas_min_idr (Rp 3.000) — or when manually triggered —
    automatically transfers funds from Trading Capital (paper_wallet) to gas_reserve_usd up to gas_target_idr (Rp 7.500).
    """
    t = get_or_init_treasury(db, usd_idr)
    current_gas_idr = t.gas_reserve_usd * usd_idr
    projected_gas_idr = (t.gas_reserve_usd - needed_gas_usd) * usd_idr

    should_topup = (force_topup_idr is not None and force_topup_idr > 0) or (projected_gas_idr < t.gas_min_idr)
    if not should_topup:
        return {
            "topped_up": False,
            "topup_usd": 0.0,
            "topup_idr": 0.0,
            "gas_reserve_usd": round(t.gas_reserve_usd, 6),
            "gas_reserve_idr": round(current_gas_idr, 0),
        }

    desired_idr = float(force_topup_idr) if (force_topup_idr and force_topup_idr > 0) else max(
        2500.0, t.gas_target_idr - current_gas_idr
    )
    desired_usd = round(desired_idr / usd_idr, 6)

    avail_cash_usd = float(paper_wallet.balance)
    actual_topup_usd = min(desired_usd, max(0.0, avail_cash_usd * 0.5)) if avail_cash_usd > 0 else desired_usd
    if actual_topup_usd <= 0:
        actual_topup_usd = desired_usd

    if avail_cash_usd >= actual_topup_usd:
        paper_wallet.balance = round(avail_cash_usd - actual_topup_usd, 6)
        paper_wallet.updated_at = datetime.now(timezone.utc)

    t.gas_reserve_usd = round(t.gas_reserve_usd + actual_topup_usd, 6)
    t.updated_at = datetime.now(timezone.utc)

    topup_row = GasTopUp(
        amount_usd=actual_topup_usd,
        source="manual_topup" if force_topup_idr else "auto_topup_trading_cash",
        balance_after_usd=t.gas_reserve_usd,
        created_at=datetime.now(timezone.utc),
    )
    db.add(topup_row)
    db.commit()
    db.refresh(t)

    try:
        from app.services import bot
        bot._append_log(
            "SYSTEM",
            "SOL",
            "GAS-RESERVE",
            f"⚡ Auto Top-Up Gas Fee +Rp {actual_topup_usd * usd_idr:,.0f} (${actual_topup_usd:.3f}) -> Saldo Gas: Rp {t.gas_reserve_usd * usd_idr:,.0f}",
            f"Target Rp {t.gas_target_idr:,.0f}",
            "info",
        )
    except Exception:
        pass

    return {
        "topped_up": True,
        "topup_usd": round(actual_topup_usd, 6),
        "topup_idr": round(actual_topup_usd * usd_idr, 0),
        "gas_reserve_usd": round(t.gas_reserve_usd, 6),
        "gas_reserve_idr": round(t.gas_reserve_usd * usd_idr, 0),
    }


def charge_gas_and_dex_fee(
    db: Session,
    paper_wallet: Wallet,
    usd_idr: float,
    gas_fee_usd: float,
    dex_fee_usd: float,
) -> TreasuryState:
    """Ensure gas reserve is sufficient (auto top-up if < Rp 3.000) and deduct gas_fee_usd."""
    ensure_gas_reserve(db, paper_wallet, usd_idr, needed_gas_usd=gas_fee_usd)
    t = get_or_init_treasury(db, usd_idr)
    t.gas_reserve_usd = max(0.0, round(t.gas_reserve_usd - gas_fee_usd, 6))
    t.total_gas_spent_usd = round((t.total_gas_spent_usd or 0.0) + gas_fee_usd, 6)
    t.total_dex_fees_usd = round((t.total_dex_fees_usd or 0.0) + dex_fee_usd, 6)
    t.updated_at = datetime.now(timezone.utc)
    # If post-deduction gas reserve dipped below minimum, auto top-up immediately so reserve stays ready
    if t.gas_reserve_usd * usd_idr < t.gas_min_idr:
        db.commit()
        ensure_gas_reserve(db, paper_wallet, usd_idr, needed_gas_usd=0.0)
        t = get_or_init_treasury(db, usd_idr)
    return t


def compute_holding_net_metrics(h: PortfolioHolding, usd_idr: float) -> dict:
    """
    Calculate both Gross and Net (after entry & exit slippage, DEX fees, and gas fees) metrics for a holding.
    Used by Portfolio Overview and Bot Auto Take-Profit / Stop-Loss so TP is 100% net of all fees!
    """
    gross_value_usd = float(h.quantity) * float(h.current_price)
    cost_usd = float(h.quantity) * float(h.avg_entry_price)  # includes entry slippage & entry DEX fee
    entry_extra_costs_usd = float(h.entry_costs_usd or 0.0)  # entry gas fee

    try:
        from app.services import bot as bot_svc
        cfg_prio = float(bot_svc._SNIPER_CONFIG.get("priority_fee_sol", 0.0008))
    except Exception:
        cfg_prio = 0.0008

    exit_costs = compute_execution_costs(
        notional_usd=gross_value_usd,
        liquidity_usd=float(h.liquidity_usd or 25000.0),
        user_slippage_pct=1.0,
        priority_fee_sol=cfg_prio,
    )
    est_exit_cost_usd = exit_costs["total_cost_usd"]
    net_value_usd = max(0.0, gross_value_usd - est_exit_cost_usd)

    gross_pnl_usd = gross_value_usd - cost_usd
    gross_pnl_pct = (gross_pnl_usd / cost_usd * 100.0) if cost_usd > 0 else 0.0

    # Net PnL subtracts entry gas + exit slippage + exit DEX fee + exit gas
    total_basis_usd = cost_usd + entry_extra_costs_usd
    net_pnl_usd = net_value_usd - total_basis_usd
    net_pnl_pct = (net_pnl_usd / total_basis_usd * 100.0) if total_basis_usd > 0 else 0.0

    return {
        "gross_value_usd": round(gross_value_usd, 6),
        "net_value_usd": round(net_value_usd, 6),
        "cost_usd": round(cost_usd, 6),
        "entry_gas_usd": round(entry_extra_costs_usd, 6),
        "est_exit_cost_usd": round(est_exit_cost_usd, 6),
        "est_exit_cost_idr": round(est_exit_cost_usd * usd_idr, 0),
        "exit_slippage_pct": exit_costs["effective_slippage_pct"],
        "exit_dex_fee_usd": exit_costs["dex_fee_usd"],
        "exit_gas_fee_usd": exit_costs["gas_fee_usd"],
        "gross_pnl_usd": round(gross_pnl_usd, 6),
        "gross_pnl_pct": round(gross_pnl_pct, 2),
        "net_pnl_usd": round(net_pnl_usd, 6),
        "net_pnl_idr": round(net_pnl_usd * usd_idr, 0),
        "net_pnl_pct": round(net_pnl_pct, 2),
    }


def record_equity_snapshot(
    db: Session,
    equity_usd: float,
    cash_usd: float,
    holdings_net_usd: float,
    gas_reserve_usd: float,
    usd_idr: float,
    reason: str = "tick",
) -> EquitySnapshot:
    snap = EquitySnapshot(
        equity_usd=round(equity_usd, 6),
        cash_usd=round(cash_usd, 6),
        holdings_net_usd=round(holdings_net_usd, 6),
        gas_reserve_usd=round(gas_reserve_usd, 6),
        usd_idr=usd_idr,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    db.commit()
    return snap


def get_main_wallet(db: Session) -> Wallet | None:
    """Return user's real Main Wallet (gate='main') if configured; never auto-create dummy wallets."""
    return (
        db.execute(
            select(Wallet)
            .where(
                Wallet.gate == "main",
                ~Wallet.name.contains("Modal Paper"),
            )
            .order_by(Wallet.id.asc())
        )
        .scalars()
        .first()
    )


def get_treasury_summary(db: Session) -> dict:
    from app.services import portfolio

    ov = portfolio.get_overview(db, refresh_live_prices=False)
    usd_idr = ov["usd_idr"]
    t = get_or_init_treasury(db, usd_idr)
    main_w = get_main_wallet(db)

    init_gas_usd = INITIAL_GAS_RESERVE_IDR / usd_idr
    # Net equity includes paper cash + net liquidation value of holdings + gas reserve delta vs initial gas reserve
    paper_cash_usd = float(ov["paper_cash_usd"])
    holdings_net_usd = float(ov.get("net_holdings_value_usd", ov["total_value"]))
    net_equity_usd = paper_cash_usd + holdings_net_usd + (t.gas_reserve_usd - init_gas_usd)
    cfg_idr = portfolio.get_paper_initial_capital_idr()
    cfg_baseline_usd = round(cfg_idr / usd_idr, 6)
    baseline_usd = float(t.baseline_equity_usd) if (t.baseline_equity_usd and float(t.baseline_equity_usd) > 0) else cfg_baseline_usd

    net_profit_usd = net_equity_usd - baseline_usd
    net_profit_pct = (net_profit_usd / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    eligible_for_transfer = net_profit_pct > t.profit_threshold_pct

    projected_to_main_usd = round(net_profit_usd * 0.40, 6) if eligible_for_transfer else 0.0
    projected_retained_60_usd = round(net_profit_usd * 0.60, 6) if eligible_for_transfer else 0.0
    projected_to_gas_usd = round(projected_retained_60_usd * (1.0 / 6.0), 6) if eligible_for_transfer else 0.0
    projected_to_capital_usd = round(projected_retained_60_usd - projected_to_gas_usd, 6) if eligible_for_transfer else 0.0

    settlements = list(
        db.execute(select(Settlement).order_by(Settlement.id.desc()).limit(10)).scalars().all()
    )
    topups = list(
        db.execute(select(GasTopUp).order_by(GasTopUp.id.desc()).limit(10)).scalars().all()
    )

    return {
        "usd_idr": usd_idr,
        "schedule_wib": "Setiap Hari Pukul 05:00 WIB (Asia/Jakarta)",
        "current_wib_time": now_wib().strftime("%Y-%m-%d %H:%M:%S WIB"),
        "next_settlement_wib": next_0500_wib_iso(),
        "last_settlement_date": t.last_settlement_date,
        "gas_reserve_usd": round(t.gas_reserve_usd, 4),
        "gas_reserve_idr": round(t.gas_reserve_usd * usd_idr, 0),
        "gas_min_idr": t.gas_min_idr,
        "gas_target_idr": t.gas_target_idr,
        "auto_topup_enabled": True,
        "total_gas_spent_usd": round(t.total_gas_spent_usd or 0.0, 4),
        "total_gas_spent_idr": round((t.total_gas_spent_usd or 0.0) * usd_idr, 0),
        "total_dex_fees_usd": round(t.total_dex_fees_usd or 0.0, 4),
        "total_dex_fees_idr": round((t.total_dex_fees_usd or 0.0) * usd_idr, 0),
        "baseline_equity_usd": round(baseline_usd, 4),
        "baseline_equity_idr": round(baseline_usd * usd_idr, 0),
        "net_equity_usd": round(net_equity_usd, 4),
        "net_equity_idr": round(net_equity_usd * usd_idr, 0),
        "net_profit_usd": round(net_profit_usd, 4),
        "net_profit_idr": round(net_profit_usd * usd_idr, 0),
        "net_profit_pct": round(net_profit_pct, 2),
        "profit_threshold_pct": t.profit_threshold_pct,
        "settlement_status_preview": "READY_TO_TRANSFER" if eligible_for_transfer else "PENDING_BELOW_40PCT",
        "projected_split": {
            "to_main_wallet_pct": 40.0,
            "to_main_wallet_usd": projected_to_main_usd,
            "to_main_wallet_idr": round(projected_to_main_usd * usd_idr, 0),
            "retained_pct": 60.0,
            "to_capital_usd": projected_to_capital_usd,
            "to_capital_idr": round(projected_to_capital_usd * usd_idr, 0),
            "to_gas_usd": projected_to_gas_usd,
            "to_gas_idr": round(projected_to_gas_usd * usd_idr, 0),
        },
        "main_wallet": {
            "id": main_w.id if main_w else None,
            "name": main_w.name if main_w else "Vault Utama Paper (Simulasi)",
            "address": main_w.address if main_w else "PAPER-MAIN-VAULT",
            "chain": main_w.chain if main_w else "Solana",
            "balance": round(main_w.balance, 4) if main_w else round(t.paper_main_vault_usd or 0.0, 4),
            "token": main_w.token if main_w else "USD",
            "paper_main_vault_usd": round(t.paper_main_vault_usd or 0.0, 4),
            "paper_main_vault_idr": round((t.paper_main_vault_usd or 0.0) * usd_idr, 0),
        },
        "settlements": [
            {
                "id": s.id,
                "settlement_date": s.settlement_date,
                "trigger": s.trigger,
                "status": s.status,
                "baseline_idr": round(s.baseline_equity_usd * s.usd_idr, 0),
                "equity_idr": round(s.equity_usd * s.usd_idr, 0),
                "net_profit_usd": round(s.net_profit_usd, 4),
                "net_profit_idr": round(s.net_profit_usd * s.usd_idr, 0),
                "net_profit_pct": round(s.net_profit_pct, 2),
                "to_main_idr": round(s.to_main_usd * s.usd_idr, 0),
                "to_capital_idr": round(s.to_capital_usd * s.usd_idr, 0),
                "to_gas_idr": round(s.to_gas_usd * s.usd_idr, 0),
                "main_wallet_address": s.main_wallet_address,
                "note": s.note,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in settlements
        ],
        "gas_topups": [
            {
                "id": g.id,
                "amount_usd": round(g.amount_usd, 4),
                "amount_idr": round(g.amount_usd * usd_idr, 0),
                "source": g.source,
                "balance_after_idr": round(g.balance_after_usd * usd_idr, 0),
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in topups
        ],
    }


def run_daily_settlement(
    db: Session,
    trigger: str = "manual",
    simulate_net_profit_idr: float | None = None,
) -> dict:
    """
    Execute the 05:00 WIB Daily Profit Settlement Rule:
    - Evaluates Net Profit (100% net after gas fees, DEX fees, and slippage) against baseline capital.
    - If Net Profit > 40%:
      * 40% is automatically transferred to Main Wallet (gate="main")
      * 60% is accumulated into Trading Capital (Modal) + Gas Fee Reserve
    - If Net Profit <= 40%:
      * Status is recorded as PENDING (no transfer, continues accumulating until > 40%).
    """
    from app.services import portfolio, bot

    paper_wallet, usd_idr = portfolio.get_or_create_paper_wallet(db)
    t = get_or_init_treasury(db, usd_idr)
    main_w = get_main_wallet(db)

    # Optional test/simulation injection if operator wants to simulate a >40% profit scenario
    if simulate_net_profit_idr is not None and float(simulate_net_profit_idr) > 0:
        add_usd = round(float(simulate_net_profit_idr) / usd_idr, 6)
        paper_wallet.balance = round(float(paper_wallet.balance) + add_usd, 6)
        paper_wallet.updated_at = datetime.now(timezone.utc)
        db.commit()

    ov = portfolio.get_overview(
        db,
        refresh_live_prices=True,
        reconcile_cash=(simulate_net_profit_idr is None),
    )
    init_gas_usd = INITIAL_GAS_RESERVE_IDR / usd_idr
    paper_cash_usd = float(ov["paper_cash_usd"])
    holdings_net_usd = float(ov.get("net_holdings_value_usd", ov["total_value"]))
    net_equity_usd = paper_cash_usd + holdings_net_usd + (t.gas_reserve_usd - init_gas_usd)
    cfg_idr = portfolio.get_paper_initial_capital_idr()
    cfg_baseline_usd = round(cfg_idr / usd_idr, 6)
    current_baseline_usd = float(t.baseline_equity_usd or 0.0)
    baseline_usd = current_baseline_usd if current_baseline_usd > 0 else cfg_baseline_usd
    if current_baseline_usd <= 0 and baseline_usd > 0:
        t.baseline_equity_usd = baseline_usd
        db.commit()

    net_profit_usd = net_equity_usd - baseline_usd
    net_profit_pct = (net_profit_usd / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    wib_date = now_wib().strftime("%Y-%m-%d")

    if net_profit_pct > t.profit_threshold_pct and net_profit_usd > 0:
        # 40% of Net Profit -> Main Wallet
        to_main_usd = round(net_profit_usd * 0.40, 6)
        # 60% of Net Profit -> Accumulated to Modal (Trading Capital) + Gas Fee Reserve
        retained_60_usd = round(net_profit_usd - to_main_usd, 6)
        to_gas_usd = round(retained_60_usd * (1.0 / 6.0), 6)  # 10% of total net profit to Gas Reserve
        to_capital_usd = round(retained_60_usd - to_gas_usd, 6)  # 50% of total net profit to Trading Capital

        # Deduct (to_main_usd + to_gas_usd) from paper_wallet cash; if cash is partially in holdings, liquidate needed portion
        needed_cash_out = to_main_usd + to_gas_usd
        if float(paper_wallet.balance) < needed_cash_out:
            holdings = list(db.execute(select(PortfolioHolding).where(PortfolioHolding.mode == "PAPER")).scalars().all())
            for h in holdings:
                if float(paper_wallet.balance) >= needed_cash_out:
                    break
                portfolio.sell_holding(db, h.symbol, 100.0, mode="PAPER")
            db.refresh(paper_wallet)

        paper_wallet.balance = max(0.0, round(float(paper_wallet.balance) - needed_cash_out, 6))
        paper_wallet.updated_at = datetime.now(timezone.utc)

        main_addr = main_w.address if (main_w and main_w.address) else "PAPER-MAIN-VAULT"
        # Credit 40% to Paper Main Vault and Simulation Main Wallet (real live wallets are funded on-chain)
        if main_w is not None and (main_w.address or "").startswith("SIMULATION"):
            main_w.balance = round(float(main_w.balance) + to_main_usd, 6)
            main_w.updated_at = datetime.now(timezone.utc)
        t.paper_main_vault_usd = round((t.paper_main_vault_usd or 0.0) + to_main_usd, 6)

        # Credit gas portion of 60% to Gas Reserve
        t.gas_reserve_usd = round(t.gas_reserve_usd + to_gas_usd, 6)
        db.add(
            GasTopUp(
                amount_usd=to_gas_usd,
                source="settlement_60pct_accumulation",
                balance_after_usd=t.gas_reserve_usd,
                created_at=datetime.now(timezone.utc),
            )
        )

        # Update baseline equity to reflect the 60% accumulated capital
        t.baseline_equity_usd = round(baseline_usd + to_capital_usd, 6)
        t.baseline_set_at = datetime.now(timezone.utc)
        t.last_settlement_date = wib_date
        t.updated_at = datetime.now(timezone.utc)

        note = (
            f"TRANSFERRED (05:00 WIB): Keuntungan bersih {net_profit_pct:+.2f}% (Rp {net_profit_usd * usd_idr:,.0f}) > 40%. "
            f"40% (Rp {to_main_usd * usd_idr:,.0f}) ditransfer ke Wallet Utama ({main_addr}), "
            f"60% diakumulasi ke Modal (+Rp {to_capital_usd * usd_idr:,.0f}) & Gas Fee (+Rp {to_gas_usd * usd_idr:,.0f})."
        )
        settlement = Settlement(
            settlement_date=wib_date,
            trigger=trigger,
            status="transferred",
            baseline_equity_usd=baseline_usd,
            equity_usd=net_equity_usd,
            net_profit_usd=net_profit_usd,
            net_profit_pct=net_profit_pct,
            to_main_usd=to_main_usd,
            to_capital_usd=to_capital_usd,
            to_gas_usd=to_gas_usd,
            main_wallet_address=main_addr,
            usd_idr=usd_idr,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
        db.add(settlement)
        db.commit()

        bot._append_log(
            "SYSTEM",
            "SOL",
            "SETTLE-05:00",
            note,
            f"Ke Main: Rp {to_main_usd * usd_idr:,.0f}",
            "success",
        )
    else:
        main_addr = main_w.address if (main_w and main_w.address) else "PAPER-MAIN-VAULT"
        t.last_settlement_date = wib_date
        t.updated_at = datetime.now(timezone.utc)
        note = (
            f"PENDING (05:00 WIB): Keuntungan bersih saat ini {net_profit_pct:+.2f}% (Rp {net_profit_usd * usd_idr:+,.0f} "
            f"setelah dipotong gas fee, DEX fee & slippage) masih di bawah target > 40%. "
            f"Transfer ke Wallet Utama ditunda (PENDING) dan saldo terus diakumulasi."
        )
        settlement = Settlement(
            settlement_date=wib_date,
            trigger=trigger,
            status="pending",
            baseline_equity_usd=baseline_usd,
            equity_usd=net_equity_usd,
            net_profit_usd=net_profit_usd,
            net_profit_pct=net_profit_pct,
            to_main_usd=0.0,
            to_capital_usd=0.0,
            to_gas_usd=0.0,
            main_wallet_address=main_addr,
            usd_idr=usd_idr,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
        db.add(settlement)
        db.commit()

        bot._append_log(
            "SYSTEM",
            "SOL",
            "SETTLE-05:00",
            note,
            f"Net Profit: {net_profit_pct:+.2f}% (<40%)",
            "warn",
        )

    return get_treasury_summary(db)


def check_and_run_0500_wib_schedule(db: Session) -> dict | None:
    """
    Automatically triggers daily settlement at or after 05:00 pagi WIB if not yet executed today.
    """
    cur = now_wib()
    today_str = cur.strftime("%Y-%m-%d")
    if cur.hour < 5:
        return None
    t = get_or_init_treasury(db)
    if t.last_settlement_date == today_str:
        return None
    return run_daily_settlement(db, trigger="schedule_0500_wib")
