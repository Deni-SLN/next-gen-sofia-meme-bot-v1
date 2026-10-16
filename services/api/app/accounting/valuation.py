"""Mark-to-market valuation for open positions (§11.2, FR-TB-007).

An open position is worth something only if there is a usable, fresh price for
it. This module is the single place that decides which mark a position gets and
what happens when there is none.

The product rule that drives every decision here: **missing data is not zero**.
A position with no snapshot, a null price, a non-finite price, or a price that
is too old to act on is reported as UNKNOWN or STALE with `unrealized_pnl =
None`. It is never reported as `0.0`, because a `0.0` here would flow into
equity, the high-water mark, the drawdown and the risk gate as if the position
were worth exactly its cost basis - which is a fabricated number, not a
measurement.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.market import MarketSnapshot, TokenPair
from app.models.trading import Position

VALUATION_KNOWN = "KNOWN"
VALUATION_STALE = "STALE"
VALUATION_UNKNOWN = "UNKNOWN"

# Statuses that carry a usable number. Everything else leaves the PnL unknown.
KNOWN_STATUSES = frozenset({VALUATION_KNOWN})


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


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class PositionValuation:
    """The mark applied to one position.

    `unrealized_pnl` is None for every status except KNOWN. `reason` is a short
    machine-readable explanation, safe to return over the API.
    """

    position_id: str
    status: str
    mark_price: float | None = None
    mark_age_seconds: float | None = None
    unrealized_pnl: float | None = None
    reason: str | None = None

    @property
    def is_known(self) -> bool:
        return self.status == VALUATION_KNOWN and self.unrealized_pnl is not None


def _latest_snapshot(db, token_id: str) -> tuple[MarketSnapshot | None, str | None]:
    """Most recent snapshot for a token's newest pair, plus a miss reason."""
    pair = (
        db.query(TokenPair)
        .filter(TokenPair.token_id == token_id)
        .order_by(TokenPair.created_at.desc())
        .first()
    )
    if pair is None:
        return None, "no_pair_for_token"
    snap = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.pair_id == pair.id)
        .order_by(MarketSnapshot.observed_at.desc())
        .first()
    )
    if snap is None:
        return None, "no_snapshot_for_pair"
    return snap, None


def unrealized_for(mark_price: float, position: Position) -> float | None:
    """Unrealized PnL at `mark_price`, or None when the inputs cannot produce one.

    Mirrors the realized formula in `trading_service.close_position`:
        gross - cost_basis - entry fees
    so closing at the mark converts unrealized into realized without a jump.
    """
    if not _finite_positive(mark_price):
        return None
    if not _finite(position.quantity) or position.quantity <= 0:
        return None
    if not _finite_positive(position.average_entry_price):
        return None
    fees = position.total_fees if _finite(position.total_fees) else None
    if fees is None:
        return None
    value = (mark_price - position.average_entry_price) * position.quantity - fees
    return value if math.isfinite(value) else None


def value_position(
    db,
    position: Position,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
) -> PositionValuation:
    """Value a single position from the freshest usable mark."""
    from app.core.config import settings

    if max_age_seconds is None:
        max_age_seconds = settings.position_mark_stale_after_seconds
    now = now or datetime.now(UTC)

    snap, miss_reason = _latest_snapshot(db, position.token_id)
    if snap is None:
        return PositionValuation(position.id, VALUATION_UNKNOWN, reason=miss_reason)

    observed_at = _aware(snap.observed_at)
    if observed_at is None:
        return PositionValuation(position.id, VALUATION_UNKNOWN, reason="snapshot_has_no_timestamp")
    age = (now - observed_at).total_seconds()

    if not _finite(snap.price_usd) or snap.price_usd is None:
        return PositionValuation(
            position.id, VALUATION_UNKNOWN, mark_age_seconds=age, reason="snapshot_price_unreadable"
        )
    if not _finite_positive(snap.price_usd):
        return PositionValuation(
            position.id,
            VALUATION_UNKNOWN,
            mark_price=float(snap.price_usd),
            mark_age_seconds=age,
            reason="snapshot_price_not_positive",
        )
    if age < 0:
        return PositionValuation(
            position.id,
            VALUATION_STALE,
            mark_price=float(snap.price_usd),
            mark_age_seconds=age,
            reason="snapshot_timestamp_in_future",
        )
    if age > max_age_seconds:
        return PositionValuation(
            position.id,
            VALUATION_STALE,
            mark_price=float(snap.price_usd),
            mark_age_seconds=age,
            reason="snapshot_stale",
        )

    pnl = unrealized_for(float(snap.price_usd), position)
    if pnl is None:
        return PositionValuation(
            position.id,
            VALUATION_UNKNOWN,
            mark_price=float(snap.price_usd),
            mark_age_seconds=age,
            reason="position_terms_invalid",
        )
    return PositionValuation(
        position.id,
        VALUATION_KNOWN,
        mark_price=float(snap.price_usd),
        mark_age_seconds=age,
        unrealized_pnl=pnl,
    )


def value_open_positions(
    db,
    mode: str,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
) -> list[PositionValuation]:
    """Value every OPEN position in a mode, oldest first."""
    rows = (
        db.query(Position)
        .filter(Position.mode == mode, Position.status == "OPEN")
        .order_by(Position.opened_at.asc())
        .all()
    )
    return [value_position(db, p, now=now, max_age_seconds=max_age_seconds) for p in rows]


def apply_valuation(db, position: Position, valuation: PositionValuation, now: datetime | None = None) -> None:
    """Persist a valuation onto the position row.

    `unrealized_pnl` is cleared to None whenever the mark is not KNOWN, so a
    previously good number cannot linger and masquerade as current.
    """
    position.valuation_status = valuation.status
    position.valuation_reason = valuation.reason
    position.mark_price = valuation.mark_price
    position.unrealized_pnl = valuation.unrealized_pnl
    position.valuation_as_of = now or datetime.now(UTC)


def refresh_open_positions(
    db,
    mode: str,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
    persist: bool = True,
) -> list[PositionValuation]:
    """Recompute and (by default) persist the valuation of every open position."""
    now = now or datetime.now(UTC)
    valuations = value_open_positions(db, mode, now=now, max_age_seconds=max_age_seconds)
    if persist:
        by_id = {v.position_id: v for v in valuations}
        rows = (
            db.query(Position)
            .filter(Position.mode == mode, Position.status == "OPEN")
            .all()
        )
        for row in rows:
            v = by_id.get(row.id)
            if v is not None:
                apply_valuation(db, row, v, now=now)
        db.commit()
    return valuations


def unknown_valuations(valuations: list[PositionValuation]) -> list[PositionValuation]:
    return [v for v in valuations if not v.is_known]


__all__ = [
    "KNOWN_STATUSES",
    "PositionValuation",
    "VALUATION_KNOWN",
    "VALUATION_STALE",
    "VALUATION_UNKNOWN",
    "apply_valuation",
    "refresh_open_positions",
    "unknown_valuations",
    "unrealized_for",
    "value_open_positions",
    "value_position",
]
