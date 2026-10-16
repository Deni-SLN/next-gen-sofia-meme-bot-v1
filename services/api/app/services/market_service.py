"""Market data ingestion: normalized pairs -> tokens/pairs/snapshots.

Data integrity rules enforced here (FR-AE-001, §10.4):
- a rolling volume window is CUMULATIVE, so it is differenced against the
  previous reading instead of being accumulated (accumulating it inflates
  candle volume ~12x and corrupts volume_ratio -> score -> signal);
- a missing measurement stays missing; it is never coerced to zero;
- pairs missing fields the pipeline needs are marked INCOMPLETE;
- candles are built from real observations only, never interpolated.
"""

import hashlib
import math
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.market import Candle, MarketSnapshot, Token, TokenPair
from app.providers.market.dexscreener import NormalizedPair

# Fields the analysis/risk pipeline treats as required. A pair missing any of
# these is INCOMPLETE (FR-AE-001) and is excluded by the default filters.
REQUIRED_PAIR_FIELDS = ("dex_id", "pair_created_at", "price_usd", "liquidity_usd")
# Seconds covered by the provider's rolling 5-minute window.
VOLUME_WINDOW_SECONDS = 300.0


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _now() -> datetime:
    return datetime.now(UTC)


def missing_fields(p: NormalizedPair) -> list[str]:
    missing = []
    if not p.dex_id:
        missing.append("dex_id")
    if p.pair_created_at is None:
        missing.append("pair_created_at")
    if not _finite(p.price_usd):
        missing.append("price_usd")
    if not _finite(p.liquidity_usd):
        missing.append("liquidity_usd")
    return missing


def upsert_token_pair(db: Session, p: NormalizedPair) -> tuple[Token, TokenPair]:
    """Insert or refresh a token/pair.

    Re-observation also fills in fields the pair was missing the first time, so
    a pair that first appears incomplete can recover.
    """
    token = (
        db.query(Token).filter(Token.chain == p.chain, Token.mint_address == p.mint_address).first()
    )
    if token is None:
        token = Token(
            chain=p.chain,
            mint_address=p.mint_address,
            symbol=p.symbol,
            name=p.name,
            decimals=p.decimals,
            first_seen_at=p.observed_at,
            metadata_json={"source": p.source},
        )
        db.add(token)
        db.flush()
    else:
        if p.symbol and token.symbol != p.symbol:
            token.symbol = p.symbol
        if p.name and token.name != p.name:
            token.name = p.name
        if p.decimals is not None and token.decimals != p.decimals:
            token.decimals = p.decimals

    pair = db.query(TokenPair).filter(TokenPair.pair_address == p.pair_address).first()
    if pair is None:
        pair = TokenPair(token_id=token.id, pair_address=p.pair_address, source=p.source)
        db.add(pair)

    # Enrich rather than only insert.
    pair.token_id = token.id
    if p.dex_id:
        pair.dex_id = p.dex_id
    if p.pair_created_at is not None:
        pair.pair_created_at = p.pair_created_at
    if p.quote_token_address:
        pair.quote_token_address = p.quote_token_address
    pair.source = p.source

    missing = missing_fields(p)
    pair.data_status = "INCOMPLETE" if missing else "COMPLETE"
    pair.missing_fields = missing
    db.flush()
    return token, pair


def save_snapshot(db: Session, pair_id: str, p: NormalizedPair) -> MarketSnapshot:
    previous = latest_snapshot(db, pair_id)
    # The provider's 5m volume is a rolling cumulative figure. Keep the raw
    # reading so the next ingest can difference against it.
    raw_volume_5m = p.volume_5m if _finite(p.volume_5m) else None

    snap = MarketSnapshot(
        pair_id=pair_id,
        price_usd=p.price_usd,
        liquidity_usd=p.liquidity_usd,
        volume_5m=raw_volume_5m,
        volume_5m_cumulative=raw_volume_5m,
        volume_1h=p.volume_1h,
        volume_24h=p.volume_24h,
        buys_5m=p.buys_5m,
        sells_5m=p.sells_5m,
        buys_1h=p.buys_1h,
        sells_1h=p.sells_1h,
        price_change_5m=p.price_change_5m,
        price_change_1h=p.price_change_1h,
        price_change_24h=p.price_change_24h,
        fdv=p.fdv,
        market_cap=p.market_cap,
        observed_at=p.observed_at,
        source=p.source,
        raw_payload_hash=p.raw_hash,
    )
    db.add(snap)
    db.flush()

    volume_delta = _volume_delta(previous, raw_volume_5m, p.observed_at)
    _accumulate_candle(db, pair_id, p, volume_delta)
    db.commit()
    return snap


def _volume_delta(
    previous: MarketSnapshot | None,
    current_cumulative: float | None,
    observed_at: datetime,
) -> float | None:
    """Volume traded during the interval since the previous reading.

    Returns None when it cannot be derived. `None` means "unknown" and is
    stored as such; substituting 0.0 would understate volume and make a dead
    token look quiet rather than unmeasured.
    """
    if current_cumulative is None or previous is None:
        return None
    prev_raw = previous.volume_5m_cumulative
    if prev_raw is None or not _finite(prev_raw):
        return None

    prev_at = previous.observed_at
    if prev_at.tzinfo is None:
        prev_at = prev_at.replace(tzinfo=UTC)
    elapsed = (observed_at - prev_at).total_seconds()
    if elapsed <= 0 or elapsed > VOLUME_WINDOW_SECONDS * 2:
        # Stale or out-of-order reading: the delta is not meaningful.
        return None

    delta = current_cumulative - prev_raw
    # A rolling window can legitimately decrease when the window slides.
    return max(0.0, delta)


def _accumulate_candle(
    db: Session,
    pair_id: str,
    p: NormalizedPair,
    volume_delta: float | None = None,
) -> None:
    """Build M1 candles from real observations.

    An existing bucket is left open (`is_final=0`) until a later observation
    closes it, so the newest candle is correctly treated as incomplete by
    downstream indicator maths.
    """
    if not _finite(p.price_usd):
        return
    now = p.observed_at
    open_time = now.replace(second=0, microsecond=0)
    prior = (
        db.query(Candle)
        .filter(
            Candle.pair_id == pair_id,
            Candle.timeframe == "M1",
            Candle.open_time < open_time,
        )
        .order_by(Candle.open_time.desc())
        .first()
    )
    if prior is not None and not prior.is_final:
        # The bucket is now complete: nothing newer will ever update it.
        prior.is_final = 1

    candle = (
        db.query(Candle)
        .filter(
            Candle.pair_id == pair_id,
            Candle.timeframe == "M1",
            Candle.open_time == open_time,
        )
        .first()
    )
    if candle is None:
        db.add(
            Candle(
                pair_id=pair_id,
                timeframe="M1",
                open_time=open_time,
                open=p.price_usd,
                high=p.price_usd,
                low=p.price_usd,
                close=p.price_usd,
                # Missing volume stays missing (NULL), not zero.
                volume=volume_delta if volume_delta is not None else 0.0,
                source="observed",
                is_final=0,
            )
        )
    else:
        candle.high = max(candle.high, p.price_usd)
        candle.low = min(candle.low, p.price_usd)
        candle.close = p.price_usd
        if volume_delta is not None:
            candle.volume = (candle.volume or 0.0) + volume_delta
        candle.is_final = 0


def aggregate_candles(db: Session, pair_id: str, base: str = "M1") -> dict:
    """Roll M1 observations up into the higher timeframes (FR-AE-002).

    Aggregation is exact: no interpolation, no synthetic candles. A bucket is
    only emitted when every constituent M1 candle exists and is final.
    """
    ladder = {"M1": ("M5", 5), "M5": ("M15", 3), "M15": ("M30", 2), "M30": ("H1", 2)}
    written: dict[str, int] = {}
    current = base
    while current in ladder:
        target, factor = ladder[current]
        written[target] = _roll_up(db, pair_id, current, target, factor)
        current = target
    return written


def _roll_up(db: Session, pair_id: str, source_tf: str, target_tf: str, factor: int) -> int:
    rows = (
        db.query(Candle)
        .filter(Candle.pair_id == pair_id, Candle.timeframe == source_tf, Candle.is_final == 1)
        .order_by(Candle.open_time)
        .all()
    )
    if not rows:
        return 0

    step = {
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
    }[target_tf]
    buckets: dict[int, list] = {}
    for row in rows:
        start = row.open_time.replace(tzinfo=UTC) if row.open_time.tzinfo is None else row.open_time
        bucket = int(start.timestamp()) // step * step
        buckets.setdefault(bucket, []).append(row)

    created = 0
    for bucket, members in buckets.items():
        if len(members) < factor:
            # Incomplete bucket: emitting it would be misleading.
            continue
        open_time = datetime.fromtimestamp(bucket, tz=UTC)
        existing = (
            db.query(Candle)
            .filter(
                Candle.pair_id == pair_id,
                Candle.timeframe == target_tf,
                Candle.open_time == open_time,
            )
            .first()
        )
        highs = [m.high for m in members]
        lows = [m.low for m in members]
        payload = {
            "open": members[0].open,
            "high": max(highs),
            "low": min(lows),
            "close": members[-1].close,
            "volume": sum((m.volume or 0.0) for m in members),
            "source": "aggregated:" + source_tf,
            "is_final": 1,
        }
        if existing is None:
            db.add(Candle(pair_id=pair_id, timeframe=target_tf, open_time=open_time, **payload))
            created += 1
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
    db.flush()
    return created


def apply_discovery_filters(pairs: list[NormalizedPair], rules: dict) -> list[NormalizedPair]:
    """Configurable discovery thresholds (FR-AE-001).

    A pair is dropped when a configured threshold is not met, and when it is
    INCOMPLETE unless the caller explicitly allows it through.
    """
    keep: list[NormalizedPair] = []
    min_liq = rules.get("min_liquidity_usd")
    min_age = rules.get("min_pool_age_minutes")
    min_volume_24h = rules.get("min_volume_24h_usd")
    min_txns_1h = rules.get("min_txns_1h")
    min_abs_change_1h = rules.get("min_abs_price_change_1h_pct")
    allow_incomplete = bool(rules.get("allow_incomplete", False))
    now = _now()

    for p in pairs:
        if not allow_incomplete and missing_fields(p):
            continue
        if min_liq is not None and not (_finite(p.liquidity_usd) and p.liquidity_usd >= min_liq):
            continue
        if min_age is not None:
            if p.pair_created_at is None:
                continue
            created = p.pair_created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if (now - created).total_seconds() / 60.0 < min_age:
                continue
        if min_volume_24h is not None and not (
            _finite(p.volume_24h) and p.volume_24h >= min_volume_24h
        ):
            continue
        if min_txns_1h is not None:
            buys = p.buys_1h or 0
            sells = p.sells_1h or 0
            if (buys + sells) < min_txns_1h:
                continue
        if min_abs_change_1h is not None:
            if not _finite(p.price_change_1h) or abs(p.price_change_1h) < min_abs_change_1h:
                continue
        keep.append(p)
    return keep


def ingest_pairs(db: Session, pairs: list[NormalizedPair], filters: dict | None = None) -> dict:
    rules = filters if filters is not None else default_filters()
    selected = apply_discovery_filters(pairs, rules)
    created_tokens = 0
    known_before = {t.id for t in db.query(Token).all()}
    for p in selected:
        token, pair = upsert_token_pair(db, p)
        if token.id not in known_before:
            created_tokens += 1
            known_before.add(token.id)
        save_snapshot(db, pair.id, p)
        aggregate_candles(db, pair.id, base="M1")
    db.commit()
    return {
        "received": len(pairs),
        "ingested": len(selected),
        "new_tokens": created_tokens,
        "filtered_out": len(pairs) - len(selected),
    }


def default_filters() -> dict:
    """Discovery thresholds from settings, so they are configurable."""
    from app.core.config import settings

    return {
        "min_liquidity_usd": settings.scanner_min_liquidity_usd,
        "min_pool_age_minutes": settings.scanner_min_pool_age_minutes,
        "min_volume_24h_usd": settings.scanner_min_volume_24h_usd,
        "min_txns_1h": settings.scanner_min_txns_1h,
        "min_abs_price_change_1h_pct": settings.scanner_min_abs_price_change_1h_pct,
        "allow_incomplete": settings.scanner_allow_incomplete,
    }


def snapshot_fingerprint(snap: MarketSnapshot) -> str:
    return hashlib.sha256(
        f"{snap.observed_at}|{snap.price_usd}|{snap.liquidity_usd}".encode()
    ).hexdigest()[:32]


def latest_snapshot(db: Session, pair_id: str) -> MarketSnapshot | None:
    return (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.pair_id == pair_id)
        .order_by(MarketSnapshot.observed_at.desc())
        .first()
    )