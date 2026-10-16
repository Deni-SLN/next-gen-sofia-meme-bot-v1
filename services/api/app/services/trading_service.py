"""Signal intake + paper execution + position lifecycle (FR-TB-003/005/007)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.analysis import Signal
from app.models.market import MarketSnapshot, TokenPair
from app.models.trading import Fill, OrderIntent, Position


def _sid_key(signal_id: str, side: str) -> str:
    return f"signal:{signal_id}:{side}"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def process_signal_for_trading(db: Session, signal_id: str) -> dict:
    """Validate an incoming signal, run the risk gate, execute in PAPER mode."""
    from app.accounting.equity import record_event, summarize_mode
    from app.risk.gate import RiskGateInput, evaluate_risk_gate
    from app.services.bot_service import (
        get_bot_state,
        get_initial_capital,
        get_risk_config,
    )

    signal = db.get(Signal, signal_id)
    if signal is None:
        raise NotFoundError("signal", signal_id)

    state = get_bot_state(db)
    mode = state["mode"]

    if signal.status in ("REJECTED", "EXPIRED", "INVALIDATED"):
        return {"accepted": False, "reason": f"signal status {signal.status}"}
    now = datetime.now(UTC)
    exp = _aware(signal.expires_at)
    if exp is not None and now > exp:
        signal.status = "EXPIRED"
        db.commit()
        return {"accepted": False, "reason": "signal expired"}
    if signal.decision != "LONG_CANDIDATE":
        return {"accepted": False, "reason": f"decision {signal.decision} not tradable"}
    if mode == "ANALYSIS_ONLY":
        return {"accepted": False, "reason": "mode ANALYSIS_ONLY does not trade"}
    if state["status"] != "RUNNING":
        return {"accepted": False, "reason": "bot not running"}

    idem_key = _sid_key(signal.id, "BUY")
    existing = db.query(OrderIntent).filter(OrderIntent.idempotency_key == idem_key).first()
    if existing is not None:
        return {"accepted": False, "reason": "duplicate signal (idempotency)", "order_id": existing.id}

    pair = db.get(TokenPair, signal.pair_id)
    snap = None
    if pair:
        snap = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.pair_id == pair.id)
            .order_by(MarketSnapshot.observed_at.desc())
            .first()
        )
    price = snap.price_usd if snap else signal.entry_reference
    liq = snap.liquidity_usd if snap else None
    data_age = (now - _aware(snap.observed_at)).total_seconds() if snap else None

    cap = get_initial_capital(db)
    eq = summarize_mode(db, mode, cap)
    open_positions = db.query(Position).filter(Position.mode == mode, Position.status == "OPEN").all()
    open_exposure = sum(p.quantity * p.average_entry_price for p in open_positions)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_pnl = sum(
        p.realized_pnl
        for p in db.query(Position)
        .filter(Position.mode == mode, Position.status == "CLOSED", Position.closed_at >= day_start)
        .all()
    )
    hard = any(
        f in ("MINT_AUTHORITY_ENABLED", "FREEZE_AUTHORITY_ENABLED", "INVALID_PRICE")
        for f in (signal.risk_flags or [])
    )

    fee_pct = (signal.fee_assumptions or {}).get("taker_fee_pct", 0.003) * 100
    slip_pct = (signal.slippage_assumption or 0.005) * 100
    impact_pct = None
    if liq and liq > 0 and signal.entry_reference:
        impact_pct = signal.entry_reference / (liq + signal.entry_reference) * 100

    decision = evaluate_risk_gate(
        RiskGateInput(
            mode=mode,
            bot_running=state["status"] == "RUNNING",
            kill_switch_active=state["kill_switch_active"],
            equity_usd=eq.equity,
            open_positions_count=len(open_positions),
            open_exposure_usd=open_exposure,
            daily_realized_pnl_usd=daily_pnl,
            peak_equity_usd=eq.high_water_mark,
            last_loss_at=_aware(datetime.fromisoformat(state["last_loss_at"])) if state.get("last_loss_at") else None,
            now=now,
            signal_created_at=_aware(signal.created_at),
            signal_expires_at=exp,
            reference_price=price,
            liquidity_usd=liq,
            slippage_pct=slip_pct,
            fee_pct=fee_pct,
            price_impact_pct=impact_pct,
            risk_reward=signal.risk_reward,
            hard_reject=hard,
            market_data_age_seconds=data_age,
            valuation_complete=eq.is_complete,
        ),
        config=get_risk_config(db),
    )

    intent = OrderIntent(
        bot_run_id=state.get("active_run_id"),
        signal_id=signal.id,
        mode=mode,
        idempotency_key=idem_key,
        side="BUY",
        requested_size=decision.sized_allocation_usd,
        reference_price=price,
        risk_decision="APPROVED" if decision.approved else "REJECTED",
        risk_reasons=decision.reasons,
        status="RISK_APPROVED" if decision.approved else "RISK_REJECTED",
    )
    db.add(intent)
    db.flush()

    if not decision.approved:
        db.commit()
        return {"accepted": False, "reason": "risk gate rejected", "order_id": intent.id, "details": decision.reasons}

    from app.execution.paper import simulate_buy

    fill = simulate_buy(
        allocation_usd=decision.sized_allocation_usd or 0.0,
        reference_price=price or 0.0,
        slippage_pct=slip_pct,
        fee_pct=fee_pct,
    )
    if fill.rejected:
        intent.status = "FAILED"
        db.commit()
        return {"accepted": False, "reason": fill.reject_reason, "order_id": intent.id}

    intent.status = "FILLED"
    position = Position(
        bot_run_id=intent.bot_run_id,
        mode=mode,
        token_id=signal.token_id,
        mint_address=signal.mint_address,
        open_order_intent_id=intent.id,
        open_signal_id=signal.id,
        status="OPEN",
        quantity=fill.quantity,
        average_entry_price=fill.price,
        total_fees=fill.fee_amount,
        # Freshly opened, not yet valued. UNKNOWN + NULL PnL is the honest
        # starting state; the valuation pass supplies a mark from then on.
        valuation_status="UNKNOWN",
        valuation_reason="awaiting_first_mark",
    )
    db.add(position)
    db.flush()
    db.add(
        Fill(
            order_id=intent.id, position_id=position.id, side="BUY",
            fill_quantity=fill.quantity, fill_price=fill.price,
            fee_amount=fill.fee_amount, slippage=fill.slippage,
            fill_type="SIMULATED",
        )
    )
    record_event(
        db, mode, "FEE", amount=fill.fee_amount, reference_type="order",
        reference_id=intent.id, idempotency_key=f"fee:{intent.id}",
    )
    record_event(
        db, mode, "TRADE_OPEN", amount=-(fill.quantity * fill.price),
        reference_type="position", reference_id=position.id,
        idempotency_key=f"open:{position.id}",
    )
    if signal.status == "CREATED":
        signal.status = "ACTIVE"
    db.commit()
    return {"accepted": True, "order_id": intent.id, "position_id": position.id, "fill_type": "SIMULATED"}


def close_position(
    db: Session, position_id: str, reason: str, price_override: float | None = None
) -> dict:
    """Close an open position, by operator request or by TP/SL.

    Delegates to `position_manager` so an operator close and an automatic exit
    follow the same claim -> fill -> finalize path and share one idempotency
    key. A position already CLOSED or being closed by someone else is a
    conflict, not a second close.
    """
    from app.services.position_manager import (
        STATUS_CLOSED,
        STATUS_OPEN,
        begin_exit,
        claim_for_exit,
        finalize_exit,
    )

    pos = db.get(Position, position_id)
    if pos is None:
        raise NotFoundError("position", position_id)
    if pos.status != STATUS_OPEN:
        raise ConflictError(
            f"position is {pos.status}, not {STATUS_OPEN}" if pos.status != STATUS_CLOSED
            else "position already closed"
        )

    pair = (
        db.query(TokenPair).filter(TokenPair.token_id == pos.token_id)
        .order_by(TokenPair.created_at.desc()).first()
    )
    price = price_override
    if price is None and pair:
        snap = (
            db.query(MarketSnapshot).filter(MarketSnapshot.pair_id == pair.id)
            .order_by(MarketSnapshot.observed_at.desc()).first()
        )
        price = snap.price_usd if snap else None
    if price is None or price <= 0:
        raise ValidationError("no valid exit price available")

    if not claim_for_exit(db, position_id):
        raise ConflictError("position already closed")
    db.refresh(pos)
    slippage_pct, fee_pct = _exit_costs(db, pos)
    begun = begin_exit(db, pos, float(price), slippage_pct, fee_pct, reason)
    if not begun["ok"]:
        raise ValidationError(f"exit not recorded: {begun['reason']}")
    finalized = finalize_exit(db, pos, reason)
    if finalized is None:
        raise ConflictError("position was already finalized")
    return finalized


def _exit_costs(db: Session, position: Position) -> tuple[float, float]:
    from app.services.position_manager import _exit_costs as _costs

    return _costs(db, position)


