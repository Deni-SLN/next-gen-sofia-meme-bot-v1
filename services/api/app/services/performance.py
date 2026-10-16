from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Trade, EquitySnapshot
from app.services import market, portfolio


def get_summary(db: Session) -> dict:
    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]
    initial_idr = portfolio.PAPER_INITIAL_CAPITAL_IDR
    initial_usd = round(initial_idr / usd_idr, 4)

    trades = list(
        db.execute(select(Trade).where(Trade.status == "closed").order_by(Trade.closed_at.asc(), Trade.id.asc()))
        .scalars()
        .all()
    )
    # Refresh live prices from DexScreener so equity curve moves in real time with market data
    port_overview = portfolio.get_overview(db, refresh_live_prices=True)
    unrealized_usd = float(port_overview.get("unrealized_pnl", 0.0))

    # Build time-series PnL & Equity curve starting from Modal Awal Rp 150.000
    pnl_chart = [
        {
            "step": 0,
            "label": "Modal Awal",
            "symbol": "INIT",
            "side": "init",
            "trade_pnl_usd": 0.0,
            "trade_pnl_idr": 0,
            "cumulative_pnl_usd": 0.0,
            "cumulative_pnl_idr": 0,
            "equity_usd": initial_usd,
            "equity_idr": initial_idr,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]

    cum_pnl_usd = 0.0
    for idx, t in enumerate(trades, start=1):
        t_pnl = float(t.pnl or 0.0)
        cum_pnl_usd += t_pnl
        eq_usd = initial_usd + cum_pnl_usd
        pnl_chart.append({
            "step": len(pnl_chart),
            "label": f"#{idx} {t.symbol.split('/')[0]}",
            "symbol": t.symbol,
            "side": t.side,
            "trade_pnl_usd": round(t_pnl, 4),
            "trade_pnl_idr": round(t_pnl * usd_idr, 0),
            "cumulative_pnl_usd": round(cum_pnl_usd, 4),
            "cumulative_pnl_idr": round(cum_pnl_usd * usd_idr, 0),
            "equity_usd": round(eq_usd, 4),
            "equity_idr": round(eq_usd * usd_idr, 0),
            "timestamp": (t.closed_at or t.opened_at or datetime.now(timezone.utc)).isoformat(),
        })

    # Include recent real-time EquitySnapshots from Neon Postgres so the chart dynamically moves with live ticks
    snapshots = list(
        db.execute(
            select(EquitySnapshot)
            .where(EquitySnapshot.reason != "reset")
            .order_by(EquitySnapshot.id.desc())
            .limit(12)
        )
        .scalars()
        .all()
    )
    snapshots.reverse()
    prev_snap_eq = pnl_chart[-1]["equity_usd"]
    for snap in snapshots:
        snap_eq_usd = float(snap.equity_usd)
        delta_usd = snap_eq_usd - prev_snap_eq
        cum_snap_usd = snap_eq_usd - initial_usd
        prev_snap_eq = snap_eq_usd
        time_lbl = snap.created_at.strftime("%H:%M:%S") if snap.created_at else "Tick"
        sym_lbl = snap.reason.split(":")[-1] if ":" in (snap.reason or "") else "LIVE"
        pnl_chart.append({
            "step": len(pnl_chart),
            "label": f"{time_lbl}",
            "symbol": sym_lbl,
            "side": "buy" if (snap.reason or "").startswith("buy") else ("sell" if (snap.reason or "").startswith("sell") else "mark"),
            "trade_pnl_usd": round(delta_usd, 4),
            "trade_pnl_idr": round(delta_usd * usd_idr, 0),
            "cumulative_pnl_usd": round(cum_snap_usd, 4),
            "cumulative_pnl_idr": round(cum_snap_usd * usd_idr, 0),
            "equity_usd": round(snap_eq_usd, 4),
            "equity_idr": round(snap_eq_usd * usd_idr, 0),
            "timestamp": (snap.created_at or datetime.now(timezone.utc)).isoformat(),
        })

    # Add current live Mark-to-Market point if there are open holdings
    if len(port_overview.get("holdings", [])) > 0 or unrealized_usd != 0.0:
        live_eq_usd = float(port_overview.get("total_equity_usd", initial_usd + cum_pnl_usd + unrealized_usd))
        live_cum_usd = live_eq_usd - initial_usd
        pnl_chart.append({
            "step": len(pnl_chart),
            "label": "Live Market",
            "symbol": "PORTFOLIO",
            "side": "mark",
            "trade_pnl_usd": round(unrealized_usd, 4),
            "trade_pnl_idr": round(unrealized_usd * usd_idr, 0),
            "cumulative_pnl_usd": round(live_cum_usd, 4),
            "cumulative_pnl_idr": round(live_cum_usd * usd_idr, 0),
            "equity_usd": round(live_eq_usd, 4),
            "equity_idr": round(live_eq_usd * usd_idr, 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    all_trades_count = len(list(db.execute(select(Trade)).scalars().all()))
    closed_count = len(trades)
    if closed_count == 0:
        return {
            "usd_idr": usd_idr,
            "total_trades": all_trades_count,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": round(unrealized_usd, 4),
            "total_pnl_idr": round(unrealized_usd * usd_idr, 0),
            "avg_pnl": 0.0,
            "avg_pnl_idr": 0,
            "best_trade": 0.0,
            "best_trade_idr": 0,
            "worst_trade": 0.0,
            "worst_trade_idr": 0,
            "pnl_chart": pnl_chart,
        }

    pnls = [float(t.pnl or 0.0) for t in trades]
    winning_trades = sum(1 for p in pnls if p > 0)
    losing_trades = closed_count - winning_trades
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / closed_count
    win_rate = (winning_trades / closed_count) * 100.0

    return {
        "usd_idr": usd_idr,
        "total_trades": all_trades_count,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 4),
        "total_pnl_idr": round(total_pnl * usd_idr, 0),
        "avg_pnl": round(avg_pnl, 4),
        "avg_pnl_idr": round(avg_pnl * usd_idr, 0),
        "best_trade": round(max(pnls), 4),
        "best_trade_idr": round(max(pnls) * usd_idr, 0),
        "worst_trade": round(min(pnls), 4),
        "worst_trade_idr": round(min(pnls) * usd_idr, 0),
        "pnl_chart": pnl_chart,
    }


def get_daily_calendar(
    db: Session,
    mode: str = "ALL",
    year: int | None = None,
    month: int | None = None,
) -> dict:
    import calendar
    from datetime import date, timedelta

    wib_tz = timezone(timedelta(hours=7))
    cur_wib = datetime.now(wib_tz)
    y = int(year) if year else cur_wib.year
    m = int(month) if month else cur_wib.month

    fx = market.get_fx_rate()
    usd_idr = fx["usd_idr"]

    stmt = select(Trade).where(Trade.status == "closed")
    mode_clean = (mode or "ALL").upper().strip()
    if mode_clean in ("PAPER", "LIVE"):
        stmt = stmt.where(Trade.mode == mode_clean)
    all_trades = list(db.execute(stmt.order_by(Trade.closed_at.desc())).scalars().all())

    # Group trades by date in WIB
    trades_by_date: dict[str, list[dict]] = {}
    for t in all_trades:
        dt = t.closed_at or t.opened_at or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        wib_date = dt.astimezone(wib_tz).strftime("%Y-%m-%d")
        t_pnl = float(t.pnl or 0.0)
        t_total = float(t.total or 0.0)
        t_fee = float(t.dex_fee_usd or 0.0) + float(t.gas_fee_usd or 0.0)
        t_slip = float(t.slippage_pct or 0.0)

        entry = {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "mode": t.mode,
            "price": t.price,
            "price_idr": round(t.price * usd_idr, 2),
            "quantity": t.quantity,
            "total_usd": round(t_total, 4),
            "total_idr": round(t_total * usd_idr, 0),
            "pnl_usd": round(t_pnl, 4),
            "pnl_idr": round(t_pnl * usd_idr, 0),
            "pnl_pct": round((t_pnl / t_total * 100.0) if t_total > 0 else 0.0, 2),
            "slippage_pct": round(t_slip, 2),
            "dex_fee_usd": round(float(t.dex_fee_usd or 0.0), 6),
            "gas_fee_usd": round(float(t.gas_fee_usd or 0.0), 6),
            "total_fee_usd": round(t_fee, 6),
            "total_fee_idr": round(t_fee * usd_idr, 0),
            "time": dt.astimezone(wib_tz).strftime("%H:%M:%S"),
            "closed_at": dt.astimezone(wib_tz).isoformat(),
        }
        trades_by_date.setdefault(wib_date, []).append(entry)

    # Days in requested month
    _, num_days = calendar.monthrange(y, m)
    days_list = []
    month_total_pnl_usd = 0.0
    month_total_volume_usd = 0.0
    month_total_fees_usd = 0.0
    month_trade_count = 0
    winning_days = 0
    losing_days = 0
    break_even_days = 0
    total_winning_trades = 0
    total_losing_trades = 0

    best_day = None
    worst_day = None

    today_str = cur_wib.strftime("%Y-%m-%d")
    is_current_month = (y == cur_wib.year and m == cur_wib.month)

    # Check if there are open holdings today
    today_unrealized_usd = 0.0
    if is_current_month and mode_clean in ("PAPER", "ALL"):
        port_ov = portfolio.get_overview(db, refresh_live_prices=False)
        today_unrealized_usd = float(port_ov.get("unrealized_pnl", 0.0))

    for day_num in range(1, num_days + 1):
        d_obj = date(y, m, day_num)
        d_str = d_obj.strftime("%Y-%m-%d")
        day_trades = trades_by_date.get(d_str, [])
        day_pnl = sum(t["pnl_usd"] for t in day_trades)
        day_volume = sum(t["total_usd"] for t in day_trades)
        day_fees = sum(t["total_fee_usd"] for t in day_trades)
        w_trades = sum(1 for t in day_trades if t["pnl_usd"] > 0)
        l_trades = sum(1 for t in day_trades if t["pnl_usd"] < 0)

        # Include floating PnL on today's cell if viewing current day
        floating_included = False
        display_pnl = day_pnl
        if d_str == today_str and len(day_trades) == 0 and today_unrealized_usd != 0.0:
            display_pnl = today_unrealized_usd
            floating_included = True

        month_total_pnl_usd += day_pnl
        month_total_volume_usd += day_volume
        month_total_fees_usd += day_fees
        month_trade_count += len(day_trades)
        total_winning_trades += w_trades
        total_losing_trades += l_trades

        if len(day_trades) > 0 or (d_str == today_str and floating_included):
            if display_pnl > 0.0001:
                winning_days += 1
            elif display_pnl < -0.0001:
                losing_days += 1
            else:
                break_even_days += 1

            if best_day is None or display_pnl > best_day["pnl_usd"]:
                best_day = {
                    "date": d_str,
                    "day_number": day_num,
                    "pnl_usd": round(display_pnl, 4),
                    "pnl_idr": round(display_pnl * usd_idr, 0),
                    "trades": len(day_trades),
                }
            if worst_day is None or display_pnl < worst_day["pnl_usd"]:
                worst_day = {
                    "date": d_str,
                    "day_number": day_num,
                    "pnl_usd": round(display_pnl, 4),
                    "pnl_idr": round(display_pnl * usd_idr, 0),
                    "trades": len(day_trades),
                }

        days_list.append({
            "date": d_str,
            "day_number": day_num,
            "weekday": d_obj.weekday(),  # 0=Monday, 6=Sunday
            "weekday_name": ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][d_obj.weekday()],
            "is_today": d_str == today_str,
            "total_pnl_usd": round(display_pnl, 4),
            "total_pnl_idr": round(display_pnl * usd_idr, 0),
            "realized_pnl_usd": round(day_pnl, 4),
            "realized_pnl_idr": round(day_pnl * usd_idr, 0),
            "floating_pnl_usd": round(today_unrealized_usd if d_str == today_str else 0.0, 4),
            "floating_included": floating_included,
            "trades_count": len(day_trades),
            "winning_trades": w_trades,
            "losing_trades": l_trades,
            "volume_usd": round(day_volume, 4),
            "volume_idr": round(day_volume * usd_idr, 0),
            "fees_usd": round(day_fees, 6),
            "fees_idr": round(day_fees * usd_idr, 0),
            "trades": day_trades,
        })

    active_days_count = winning_days + losing_days + break_even_days
    day_win_rate = (winning_days / active_days_count * 100.0) if active_days_count > 0 else 0.0
    trade_win_rate = (total_winning_trades / month_trade_count * 100.0) if month_trade_count > 0 else 0.0

    month_names_id = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]

    return {
        "usd_idr": usd_idr,
        "mode": mode_clean,
        "year": y,
        "month": m,
        "month_label": f"{month_names_id[m]} {y}",
        "summary": {
            "total_pnl_usd": round(month_total_pnl_usd, 4),
            "total_pnl_idr": round(month_total_pnl_usd * usd_idr, 0),
            "total_volume_usd": round(month_total_volume_usd, 4),
            "total_volume_idr": round(month_total_volume_usd * usd_idr, 0),
            "total_fees_usd": round(month_total_fees_usd, 6),
            "total_fees_idr": round(month_total_fees_usd * usd_idr, 0),
            "total_trades": month_trade_count,
            "total_winning_trades": total_winning_trades,
            "total_losing_trades": total_losing_trades,
            "trade_win_rate_pct": round(trade_win_rate, 2),
            "winning_days": winning_days,
            "losing_days": losing_days,
            "break_even_days": break_even_days,
            "active_days": active_days_count,
            "day_win_rate_pct": round(day_win_rate, 2),
            "best_day": best_day,
            "worst_day": worst_day,
        },
        "days": days_list,
    }

