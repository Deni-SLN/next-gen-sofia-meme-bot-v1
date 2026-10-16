"""Append-only accounting ledger and canonical equity model (§11.2).

Canonical: equity = initial_capital + realized_pnl + unrealized_pnl - external_cash_movements

Convention (documented once, used everywhere): a POSITIVE external cash
movement amount means money leaving the ledger (withdrawal); a NEGATIVE
amount means money entering (deposit). This makes the minus sign in the
canonical formula read naturally as "subtract money that left".

Unrealized PnL comes from `app.accounting.valuation` and is deliberately
nullable. When any open position lacks a usable mark, `unrealized_pnl`,
`equity` and `current_drawdown_pct` are None and `valuation_status` is
`INCOMPLETE` - they are never backfilled with a number that was not measured.
`known_unrealized_pnl` still reports the measurable part so an operator can see
how much of the book is actually valued.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from app.accounting.valuation import (
    refresh_open_positions,
    unknown_valuations,
)
from app.models.trading import AccountingEvent

VALUATION_COMPLETE = "COMPLETE"
VALUATION_INCOMPLETE = "INCOMPLETE"


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


@dataclass
class EquitySnapshot:
    initial_capital: float
    realized_pnl: float
    unrealized_pnl: float | None
    external_cash_movements: float
    equity: float | None
    high_water_mark: float
    current_drawdown_pct: float | None
    # COMPLETE when every open position is valued; INCOMPLETE otherwise.
    valuation_status: str = VALUATION_COMPLETE
    # Positions without a usable mark. Drives the risk gate's fail-closed rule.
    unmarked_positions: int = 0
    # Sum over valued positions only. Present even when valuation_status is
    # INCOMPLETE so the operator can see the floor, never as "the" number.
    known_unrealized_pnl: float = 0.0

    @property
    def is_complete(self) -> bool:
        return self.valuation_status == VALUATION_COMPLETE

    @property
    def known_equity(self) -> float:
        """Equity counting only the measured part of the book."""
        return self.initial_capital + self.realized_pnl + self.known_unrealized_pnl - self.external_cash_movements



def compute_equity(
    initial_capital: float,
    realized_pnl: float,
    unrealized_pnl: float,
    external_cash_movements: float,
) -> float:
    if not all(_finite(v) for v in (initial_capital, realized_pnl, unrealized_pnl, external_cash_movements)):
        raise ValueError("non-finite value in equity computation")
    return initial_capital + realized_pnl + unrealized_pnl - external_cash_movements


def record_event(
    db,
    mode: str,
    event_type: str,
    amount: float = 0.0,
    reference_type: str | None = None,
    reference_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict | None = None,
) -> AccountingEvent | None:
    """Append an accounting event. Idempotency key prevents double accounting on retry."""
    if not _finite(amount):
        raise ValueError("accounting amount must be finite")
    if idempotency_key:
        existing = (
            db.query(AccountingEvent)
            .filter(AccountingEvent.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return None  # duplicate suppressed
    ev = AccountingEvent(
        mode=mode,
        event_type=event_type,
        amount=amount,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        metadata_json=metadata or {},
    )
    db.add(ev)
    db.commit()
    return ev


def summarize_mode(
    db,
    mode: str,
    initial_capital: float,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
    persist_valuation: bool = True,
) -> EquitySnapshot:
    """Summarize a mode's equity, valuing open positions first.

    Every open position is marked before the snapshot is taken, so equity can
    never be reported while the book is unvalued.
    """
    valuations = refresh_open_positions(
        db, mode, now=now, max_age_seconds=max_age_seconds, persist=persist_valuation
    )
    known = [v for v in valuations if v.is_known]
    missing = unknown_valuations(valuations)

    realized = sum(
        e.amount
        for e in db.query(AccountingEvent)
        .filter(AccountingEvent.mode == mode, AccountingEvent.event_type == "REALIZED_PNL")
        .all()
    )
    external = sum(
        e.amount
        for e in db.query(AccountingEvent)
        .filter(
            AccountingEvent.mode == mode,
            AccountingEvent.event_type.in_(["DEPOSIT", "WITHDRAWAL"]),
        )
        .all()
    )
    known_unrealized = sum(v.unrealized_pnl for v in known)

    if missing:
        # An unvalued position makes the total unknown. Reporting 0 here would
        # understate risk: the position could be at a loss as easily as a gain.
        status = VALUATION_INCOMPLETE
        unrealized = None
        equity = None
    else:
        status = VALUATION_COMPLETE
        unrealized = known_unrealized
        equity = compute_equity(initial_capital, realized, unrealized, external)

    known_equity = compute_equity(initial_capital, realized, known_unrealized, external)
    # The high-water mark is a historical maximum, so it stays well defined even
    # when current equity is unknown. The known-equity floor keeps it monotone.
    hwm = _high_water_mark(db, mode, initial_capital, known_equity)
    dd = (hwm - equity) / hwm * 100 if equity is not None and hwm > 0 else None
    return EquitySnapshot(
        initial_capital=initial_capital,
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        external_cash_movements=external,
        equity=equity,
        high_water_mark=hwm,
        current_drawdown_pct=dd,
        valuation_status=status,
        unmarked_positions=len(missing),
        known_unrealized_pnl=known_unrealized,
    )


def _high_water_mark(db, mode: str, initial_capital: float, current_equity: float) -> float:
    running = initial_capital
    peak = initial_capital
    for e in (
        db.query(AccountingEvent)
        .filter(AccountingEvent.mode == mode)
        .order_by(AccountingEvent.created_at)
        .all()
    ):
        # Reconstruct equity through time and keep the running maximum.
        # Tracking only the final value would make the high-water mark equal to
        # current equity, so drawdown would always read 0%.
        if e.event_type == "REALIZED_PNL":
            running += e.amount
        elif e.event_type == "WITHDRAWAL":
            running -= e.amount
        elif e.event_type == "DEPOSIT":
            running -= e.amount  # deposits are stored negative
        peak = max(peak, running)
    return max(peak, current_equity)


def equity_curve(db, mode: str, initial_capital: float) -> list[dict]:
    """Reconstruct the realized equity path from append-only events.

    Intermediate points are the ledger path, which is fully determined by the
    events. The live valuation of open positions is not historical, so it is
    attached to the final point only, where it is still true. When the book is
    unvalued the final `equity` is None rather than the realized-only number -
    the ledger path is still available as `realized_equity` on every point.
    """
    events = (
        db.query(AccountingEvent)
        .filter(AccountingEvent.mode == mode)
        .order_by(AccountingEvent.created_at)
        .all()
    )
    snap = summarize_mode(db, mode, initial_capital)
    realized = 0.0
    external = 0.0
    curve = [
        {
            "timestamp": None,
            "equity": initial_capital,
            "realized_equity": initial_capital,
            "realized_pnl": 0.0,
            "label": "start",
        }
    ]
    for e in events:
        if e.event_type == "REALIZED_PNL":
            realized += e.amount
        elif e.event_type in ("DEPOSIT", "WITHDRAWAL"):
            external += e.amount
        ledger_equity = compute_equity(initial_capital, realized, 0.0, external)
        curve.append(
            {
                "timestamp": e.created_at.isoformat() if isinstance(e.created_at, datetime) else None,
                "equity": round(ledger_equity, 6),
                "realized_equity": round(ledger_equity, 6),
                "realized_pnl": round(realized, 6),
                "label": e.event_type,
            }
        )
    if len(curve) > 1:
        # Only the last point of a non-trivial path carries the live valuation.
        curve[-1].update(
            {
                "equity": None if snap.equity is None else round(snap.equity, 6),
                "unrealized_pnl": None if snap.unrealized_pnl is None else round(snap.unrealized_pnl, 6),
                "valuation_status": snap.valuation_status,
                "label": "current",
            }
        )
    return curve
