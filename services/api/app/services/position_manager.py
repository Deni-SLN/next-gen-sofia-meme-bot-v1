"""Automatic position exits with TP/SL (FR-TB-007).

Before this module nothing ever closed a position automatically: `close_reason`
was always `operator_close`, and a position could ride until a human noticed.

Two properties matter more than the strategy itself:

**Fail closed on unknown data.** An exit is only ever taken on a mark the
valuation pass called KNOWN - a real, finite, fresh price. A missing, stale or
unreadable mark produces HOLD with a reason. It never triggers a stop-loss out
of nothing, and it never silently strands the position either: the reason is
recorded so the operator can see why it is still open.

**Two-phase close.** Claiming a position for exit, writing the fill, updating
the position and writing the ledger are separate committed steps. A crash
between them leaves a position in CLOSING that `recover_stalled_exits` can
finish or roll back, rather than a position that is half closed with no record
of which half happened.

Live execution is not reachable from here. Every fill this module produces is
SIMULATED, and the caller must already be in PAPER mode.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.analysis import Signal
from app.models.trading import Fill, OrderIntent, Position

# Position status transitions (mirrors `Position.status`).
STATUS_OPEN = "OPEN"
STATUS_CLOSING = "CLOSING"
STATUS_CLOSED = "CLOSED"

# What an evaluation decided to do.
ACTION_HOLD = "HOLD"
ACTION_TAKE_PROFIT = "TAKE_PROFIT"
ACTION_STOP_LOSS = "STOP_LOSS"

PLAN_SIGNAL = "SIGNAL"
PLAN_PERCENT_FALLBACK = "PERCENT_FALLBACK"
PLAN_NONE = "NONE"

# `close_position(reason=...)` values this module produces.
REASON_TAKE_PROFIT = "take_profit"
REASON_STOP_LOSS = "stop_loss"

EXIT_IDEMPOTENCY_PREFIX = "exit:"


def exit_idempotency_key(position_id: str) -> str:
    return f"{EXIT_IDEMPOTENCY_PREFIX}{position_id}"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _finite_positive(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _finite(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


@dataclass(frozen=True)
class ExitPlan:
    """Where this position should stop out and take profit."""

    stop_price: float | None = None
    target_prices: tuple[float, ...] = ()
    source: str = PLAN_NONE

    @property
    def is_usable(self) -> bool:
        return self.stop_price is not None or bool(self.target_prices)


@dataclass(frozen=True)
class ExitDecision:
    action: str
    reason: str
    mark_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    unrealized_pnl: float | None = None
    plan_source: str = PLAN_NONE
    details: dict = field(default_factory=dict)

    @property
    def should_exit(self) -> bool:
        return self.action in (ACTION_TAKE_PROFIT, ACTION_STOP_LOSS)


def exit_plan(db: Session, position: Position) -> ExitPlan:
    """Resolve the exit levels for a position.

    The signal's own plan wins: it encodes the ATR/support-derived stop that
    the analysis actually reasoned about. Percentages are a fallback for a
    position whose signal is silent - and when neither exists the plan is
    unusable, which means HOLD rather than a guessed exit.
    """
    from app.core.config import settings

    signal = db.get(Signal, position.open_signal_id) if position.open_signal_id else None
    if signal is not None:
        stops: list[float] = []
        if _finite_positive(signal.stop_reference):
            stops.append(float(signal.stop_reference))
        targets = tuple(
            float(t) for t in (signal.target_references or []) if _finite_positive(t)
        )
        if stops or targets:
            # A stop above the entry is not a stop; ignore it rather than
            # inheriting an inverted plan.
            entry = position.average_entry_price
            valid_stops = [s for s in stops if s < entry] if _finite_positive(entry) else stops
            return ExitPlan(
                stop_price=min(valid_stops) if valid_stops else None,
                target_prices=tuple(sorted(t for t in targets if not _finite_positive(entry) or t > entry)),
                source=PLAN_SIGNAL,
            )

    entry = position.average_entry_price
    if not _finite_positive(entry):
        return ExitPlan(source=PLAN_NONE)

    stop = entry * (1.0 - abs(settings.position_stop_loss_pct) / 100.0)
    target = entry * (1.0 + abs(settings.position_take_profit_pct) / 100.0)
    if not _finite_positive(stop) or not _finite_positive(target) or target <= entry:
        return ExitPlan(source=PLAN_NONE)
    return ExitPlan(stop_price=stop, target_prices=(target,), source=PLAN_PERCENT_FALLBACK)


def evaluate_exit(
    position: Position,
    plan: ExitPlan,
    valuation,
) -> ExitDecision:
    """Decide whether an open position should be closed right now.

    `valuation` is a `PositionValuation`. Anything other than KNOWN holds the
    position: acting on an unknown price is exactly the mistake this codebase
    refuses everywhere else.
    """
    if valuation is None or not valuation.is_known:
        reason = getattr(valuation, "reason", None) or "no valuation"
        return ExitDecision(
            action=ACTION_HOLD,
            reason=f"hold: valuation {getattr(valuation, 'status', 'MISSING')} ({reason})",
            mark_price=getattr(valuation, "mark_price", None),
            plan_source=plan.source,
        )

    mark = valuation.mark_price
    if not _finite_positive(mark):
        return ExitDecision(
            action=ACTION_HOLD,
            reason="hold: mark price unusable",
            plan_source=plan.source,
        )

    if not plan.is_usable:
        return ExitDecision(
            action=ACTION_HOLD,
            reason="hold: no exit plan for this position",
            mark_price=mark,
            unrealized_pnl=valuation.unrealized_pnl,
            plan_source=plan.source,
        )

    if plan.stop_price is not None and mark <= plan.stop_price:
        return ExitDecision(
            action=ACTION_STOP_LOSS,
            reason=f"mark {mark:.6g} at or below stop {plan.stop_price:.6g}",
            mark_price=mark,
            stop_price=plan.stop_price,
            unrealized_pnl=valuation.unrealized_pnl,
            plan_source=plan.source,
        )

    for target in plan.target_prices:
        if mark >= target:
            return ExitDecision(
                action=ACTION_TAKE_PROFIT,
                reason=f"mark {mark:.6g} at or above target {target:.6g}",
                mark_price=mark,
                target_price=target,
                unrealized_pnl=valuation.unrealized_pnl,
                plan_source=plan.source,
            )

    return ExitDecision(
        action=ACTION_HOLD,
        reason="mark is inside the exit band",
        mark_price=mark,
        stop_price=plan.stop_price,
        unrealized_pnl=valuation.unrealized_pnl,
        plan_source=plan.source,
    )


# --------------------------- two-phase close ---------------------------


def claim_for_exit(db: Session, position_id: str) -> bool:
    """Atomically move OPEN -> CLOSING. True for exactly one caller.

    The `WHERE status = 'OPEN'` predicate is the concurrency guard: two workers
    racing on the same position produce one rowcount of 1 and one of 0, so the
    second caller is a no-op instead of a double close.
    """
    result = db.execute(
        update(Position)
        .where(Position.id == position_id, Position.status == STATUS_OPEN)
        .values(status=STATUS_CLOSING)
    )
    db.commit()
    return result.rowcount == 1


def release_from_exit(db: Session, position_id: str, reason: str | None = None) -> bool:
    """Move CLOSING -> OPEN, for an exit that did not happen."""
    # String column names, not mapped attributes: `.values(**...)` unpacks to
    # keyword arguments, which cannot be mapped-attribute objects.
    values: dict = {"status": STATUS_OPEN}
    if reason:
        values["close_reason"] = reason
    result = db.execute(
        update(Position)
        .where(Position.id == position_id, Position.status == STATUS_CLOSING)
        .values(**values)
    )
    db.commit()
    return result.rowcount == 1


def get_exit_intent(db: Session, position_id: str) -> OrderIntent | None:
    return (
        db.query(OrderIntent)
        .filter(OrderIntent.idempotency_key == exit_idempotency_key(position_id))
        .first()
    )


def get_exit_fill(db: Session, intent_id: str) -> Fill | None:
    return db.query(Fill).filter(Fill.order_id == intent_id).first()


def begin_exit(
    db: Session,
    position: Position,
    mark_price: float,
    slippage_pct: float,
    fee_pct: float,
    reason: str,
) -> dict:
    """Phase 1: claim, create the exit intent, write the fill, commit.

    Everything a recovery needs is durable once this returns. The position is
    still CLOSING and still holds its full quantity; phase 2 turns it into a
    closed trade.
    """
    from app.execution.paper import simulate_sell

    fill = simulate_sell(
        quantity=position.quantity,
        reference_price=mark_price,
        slippage_pct=slippage_pct,
        fee_pct=fee_pct,
    )
    if fill.rejected:
        release_from_exit(db, position.id)
        return {"ok": False, "reason": fill.reject_reason}

    intent = OrderIntent(
        bot_run_id=position.bot_run_id,
        signal_id=position.open_signal_id or position.id,
        mode=position.mode,
        idempotency_key=exit_idempotency_key(position.id),
        side="SELL",
        requested_size=position.quantity * position.average_entry_price,
        reference_price=mark_price,
        risk_decision="APPROVED",
        risk_reasons=[reason],
        status="FILLED",
    )
    db.add(intent)
    try:
        db.flush()
    except IntegrityError:
        # Another worker got the exit intent in first. Unique constraint on
        # idempotency_key is the arbiter.
        db.rollback()
        return {"ok": False, "reason": "exit already recorded (idempotency)"}

    db.add(
        Fill(
            order_id=intent.id,
            position_id=position.id,
            side="SELL",
            fill_quantity=fill.quantity,
            fill_price=fill.price,
            fee_amount=fill.fee_amount,
            slippage=fill.slippage,
            fill_type="SIMULATED",
        )
    )
    db.commit()  # phase 1 is durable here
    return {
        "ok": True,
        "intent_id": intent.id,
        "fill_price": fill.price,
        "fill_quantity": fill.quantity,
        "fee_amount": fill.fee_amount,
        "reason": reason,
    }


def finalize_exit(db: Session, position: Position, reason: str) -> dict | None:
    """Phase 2: turn a claimed position with a recorded fill into a closed trade.

    Idempotent: the ledger writes carry per-position idempotency keys, and a
    position that is already CLOSED is left alone.
    """
    from app.accounting.equity import record_event

    db.refresh(position)
    if position.status == STATUS_CLOSED:
        return None

    intent = get_exit_intent(db, position.id)
    if intent is None or intent.status != "FILLED":
        release_from_exit(db, position.id)
        return None
    fill = get_exit_fill(db, intent.id)
    if fill is None:
        release_from_exit(db, position.id)
        return None

    gross = fill.fill_quantity * fill.fill_price
    cost_basis = position.quantity * position.average_entry_price
    realized = gross - cost_basis - fill.fee_amount - position.total_fees

    position.status = STATUS_CLOSED
    position.realized_pnl = realized
    position.exit_price = fill.fill_price
    position.close_reason = reason
    position.closed_at = datetime.now(UTC)
    position.total_fees += fill.fee_amount
    position.exit_order_intent_id = intent.id
    position.mark_price = fill.fill_price
    position.unrealized_pnl = 0.0
    position.valuation_status = "KNOWN"
    position.valuation_reason = "closed_at_exit_price"
    position.valuation_as_of = position.closed_at
    db.commit()

    record_event(db, position.mode, "TRADE_CLOSE", amount=gross, reference_type="position",
                 reference_id=position.id, idempotency_key=f"close:{position.id}")
    record_event(db, position.mode, "REALIZED_PNL", amount=realized, reference_type="position",
                 reference_id=position.id, idempotency_key=f"pnl:{position.id}")
    record_event(db, position.mode, "FEE", amount=fill.fee_amount, reference_type="position",
                 reference_id=position.id, idempotency_key=f"closefee:{position.id}")

    if realized < 0:
        from app.services.bot_service import get_bot_state, save_bot_state

        state = get_bot_state(db)
        state["last_loss_at"] = datetime.now(UTC).isoformat()
        save_bot_state(db, state)

    _offer_profit_sweep(db, position, realized)

    return {"position_id": position.id, "realized_pnl": realized, "exit_price": fill.fill_price,
            "fill_type": "SIMULATED"}


def _offer_profit_sweep(db: Session, position: Position, realized: float) -> None:
    """Hand a profitable close to the sweep evaluator.

    This is the trigger that did not exist: `evaluate_and_record_sweep` was only
    reachable from tests, so the automatic mode of PRD v1.1 could never run in
    production. It is itself idempotent on the close event, so calling it from
    here cannot double-sweep.

    Failures are swallowed and logged: a sweep problem must not turn a
    successful exit into a failed close.
    """
    if realized <= 0:
        return
    from app.core.logging import get_logger
    from app.services.wallet_service import evaluate_and_record_sweep, get_main_wallet

    try:
        wallet = get_main_wallet(db)
        if wallet is None:
            get_logger("position_manager").info(
                "no MAIN wallet registered; profit of %.6f not offered for sweep", realized
            )
            return
        for asset in ("SOL", "USDC"):
            result = evaluate_and_record_sweep(
                db, "system", f"position:{position.id}", wallet.id, asset
            )
            get_logger("position_manager").info(
                "sweep %s for position %s: %s", asset, position.id, result.get("status")
            )
    except Exception:  # noqa: BLE001
        get_logger("position_manager").exception(
            "sweep evaluation failed for position %s", position.id
        )


# --------------------------- recovery ---------------------------


def recover_stalled_exits(
    db: Session,
    mode: str,
    now: datetime | None = None,
    older_than_seconds: int | None = None,
) -> list[dict]:
    """Reconcile positions stranded in CLOSING by a crash.

    Three outcomes, decided by what is actually durable:
      * intent + fill present -> finish phase 2 (the trade really happened)
      * claim only             -> roll back to OPEN (nothing happened)
      * intent without fill   -> roll back and mark the intent FAILED

    A position younger than the threshold is left alone: its worker may still
    be mid-write, and stealing it would create the race recovery prevents.
    """
    from app.core.config import settings

    now = now or datetime.now(UTC)
    threshold = timedelta(
        seconds=older_than_seconds if older_than_seconds is not None
        else settings.position_exit_recovery_seconds
    )
    recovered: list[dict] = []
    stalled = (
        db.query(Position)
        .filter(Position.mode == mode, Position.status == STATUS_CLOSING)
        .all()
    )
    for position in stalled:
        updated_at = _aware(position.updated_at)
        if updated_at is not None and (now - updated_at) < threshold:
            continue

        intent = get_exit_intent(db, position.id)
        if intent is not None and intent.status == "FILLED" and get_exit_fill(db, intent.id):
            result = finalize_exit(db, position, reason=position.close_reason or "recovered_exit")
            recovered.append(
                {"position_id": position.id, "action": "finalized", "detail": result or {}}
            )
            continue

        if intent is not None:
            intent.status = "FAILED"
            db.commit()
        release_from_exit(db, position.id)
        recovered.append({"position_id": position.id, "action": "rolled_back"})
    return recovered


# --------------------------- the sweep ---------------------------


def _exit_costs(db: Session, position: Position) -> tuple[float, float]:
    """Exit slippage/fee in percent, from the signal that opened the trade."""
    signal = db.get(Signal, position.open_signal_id) if position.open_signal_id else None
    if signal is None:
        return 0.5, 0.3
    taker_fee = (signal.fee_assumptions or {}).get("taker_fee_pct", 0.003)
    fee_pct = float(taker_fee) * 100
    slip = signal.slippage_assumption
    slippage_pct = float(slip) * 100 if slip is not None else 0.5
    return slippage_pct, fee_pct


def run_position_lifecycle(
    db: Session,
    mode: str = "PAPER",
    now: datetime | None = None,
    max_age_seconds: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Recover stranded exits, then close whatever TP/SL says to close.

    Refuses to run outside PAPER: this module has no live path and should not
    gain one by accident.
    """
    from app.accounting.valuation import refresh_open_positions
    from app.services.bot_service import get_bot_state

    if mode != "PAPER":
        return {"ok": False, "error": "position lifecycle runs in PAPER mode only"}

    state = get_bot_state(db)
    if state.get("status") != "RUNNING":
        return {"ok": True, "skipped": "bot is not running", "closed": [], "held": []}
    if state.get("kill_switch_active"):
        return {"ok": True, "skipped": "kill switch active", "closed": [], "held": []}

    now = now or datetime.now(UTC)
    recovered = recover_stalled_exits(db, mode, now=now)

    valuations = {
        v.position_id: v
        for v in refresh_open_positions(db, mode, now=now, max_age_seconds=max_age_seconds)
    }

    closed: list[dict] = []
    held: list[dict] = []
    positions = (
        db.query(Position)
        .filter(Position.mode == mode, Position.status == STATUS_OPEN)
        .order_by(Position.opened_at.asc())
        .all()
    )

    for position in positions:
        valuation = valuations.get(position.id)
        plan = exit_plan(db, position)
        decision = evaluate_exit(position, plan, valuation)

        if not decision.should_exit:
            held.append(
                {
                    "position_id": position.id,
                    "action": decision.action,
                    "reason": decision.reason,
                    "plan_source": decision.plan_source,
                }
            )
            continue

        if dry_run:
            closed.append(
                {
                    "position_id": position.id,
                    "action": decision.action,
                    "reason": decision.reason,
                    "dry_run": True,
                }
            )
            continue

        reason = REASON_TAKE_PROFIT if decision.action == ACTION_TAKE_PROFIT else REASON_STOP_LOSS
        if not claim_for_exit(db, position.id):
            held.append({"position_id": position.id, "action": "HOLD", "reason": "lost the claim race"})
            continue
        db.refresh(position)
        slippage_pct, fee_pct = _exit_costs(db, position)
        begun = begin_exit(db, position, decision.mark_price, slippage_pct, fee_pct, reason)
        if not begun["ok"]:
            held.append({"position_id": position.id, "action": "HOLD", "reason": begun["reason"]})
            continue
        finalized = finalize_exit(db, position, reason)
        if finalized is None:
            held.append({"position_id": position.id, "action": "HOLD", "reason": "finalize skipped"})
            continue
        closed.append(
            {
                "position_id": position.id,
                "action": decision.action,
                "reason": decision.reason,
                "close_reason": reason,
                "realized_pnl": finalized["realized_pnl"],
                "exit_price": finalized["exit_price"],
                "fill_type": finalized["fill_type"],
            }
        )

    return {
        "ok": True,
        "mode": mode,
        "closed": closed,
        "held": held,
        "recovered": recovered,
        "dry_run": dry_run,
    }


__all__ = [
    "ACTION_HOLD",
    "ACTION_STOP_LOSS",
    "ACTION_TAKE_PROFIT",
    "ExitDecision",
    "ExitPlan",
    "PLAN_NONE",
    "PLAN_PERCENT_FALLBACK",
    "PLAN_SIGNAL",
    "REASON_STOP_LOSS",
    "REASON_TAKE_PROFIT",
    "STATUS_CLOSED",
    "STATUS_CLOSING",
    "STATUS_OPEN",
    "begin_exit",
    "claim_for_exit",
    "evaluate_exit",
    "exit_idempotency_key",
    "exit_plan",
    "finalize_exit",
    "get_exit_fill",
    "get_exit_intent",
    "recover_stalled_exits",
    "release_from_exit",
    "run_position_lifecycle",
]
