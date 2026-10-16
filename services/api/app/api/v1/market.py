"""Market & analysis endpoints (FR §12.2)."""

from datetime import UTC, datetime

from app.api.v1.deps import current_actor, require_operator
from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.db.session import get_db
from app.models.analysis import RiskAssessment
from app.models.market import Candle, Token, TokenPair
from app.providers.market.dexscreener import DexScreenerProvider
from app.services.market_service import ingest_pairs, latest_snapshot
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(tags=["market"])
_dex = DexScreenerProvider()

# PRD §4 / FR-AE-002: only timeframes the stored data can actually support.
SUPPORTED_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def _pair_json(p) -> dict:
    return {
        "chain": p.chain,
        "mint_address": p.mint_address,
        "pair_address": p.pair_address,
        "symbol": p.symbol,
        "name": p.name,
        "dex_id": p.dex_id,
        "price_usd": p.price_usd,
        "liquidity_usd": p.liquidity_usd,
        "volume_5m": p.volume_5m,
        "volume_1h": p.volume_1h,
        "volume_24h": p.volume_24h,
        "buys_1h": p.buys_1h,
        "sells_1h": p.sells_1h,
        "price_change_5m": p.price_change_5m,
        "price_change_1h": p.price_change_1h,
        "price_change_24h": p.price_change_24h,
        "fdv": p.fdv,
        "market_cap": p.market_cap,
        "pair_created_at": p.pair_created_at.isoformat() if p.pair_created_at else None,
        "observed_at": p.observed_at.isoformat() if p.observed_at else None,
        "source": p.source,
    }


@router.get("/discover/search")
def discover_search(q: str, limit: int = Query(20, le=50), actor: str = Depends(current_actor)):
    """Live market discovery via DEX Screener (FR §10.1). Provider errors surfaced clearly."""
    import asyncio

    try:
        pairs = asyncio.run(_dex.search(q, limit=limit))
    except ProviderError as e:
        return {"items": [], "error": str(e.message), "source": "dexscreener"}
    return {"items": [_pair_json(p) for p in pairs], "source": "dexscreener"}


@router.get("/discover/trending")
def discover_trending(limit: int = Query(20, le=50), actor: str = Depends(current_actor)):
    import asyncio

    try:
        pairs = asyncio.run(_dex.trending(limit=limit))
    except ProviderError as e:
        return {"items": [], "error": str(e.message), "source": "dexscreener"}
    return {"items": [_pair_json(p) for p in pairs], "source": "dexscreener"}


@router.post("/discover/ingest")
def discover_ingest(q: str, limit: int = Query(20, le=50), db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    """Discover + persist tokens/pairs/snapshots into the local DB for analysis/backtest."""
    import asyncio

    try:
        pairs = asyncio.run(_dex.search(q, limit=limit))
    except ProviderError as e:
        return {"ingested": 0, "error": str(e.message)}
    return ingest_pairs(db, pairs)


@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    q: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    actor: str = Depends(current_actor),
):
    query = db.query(Token)
    if q:
        like = f"%{q}%"
        query = query.filter((Token.symbol.ilike(like)) | (Token.mint_address.ilike(like)))
    total = query.count()
    tokens = query.order_by(Token.created_at.desc()).offset(offset).limit(limit).all()
    now = datetime.now(UTC)
    out = []
    for t in tokens:
        pair = db.query(TokenPair).filter(TokenPair.token_id == t.id).order_by(TokenPair.created_at.desc()).first()
        snap = latest_snapshot(db, pair.id) if pair else None
        age = None
        stale = True
        if snap:
            obs = snap.observed_at if snap.observed_at.tzinfo else snap.observed_at.replace(tzinfo=UTC)
            age = (now - obs).total_seconds()
            stale = age > settings.market_stale_after_seconds
        out.append({
            "id": t.id, "chain": t.chain, "mint_address": t.mint_address, "symbol": t.symbol,
            "name": t.name, "first_seen_at": t.first_seen_at.isoformat() if t.first_seen_at else None,
            "pair": {"pair_address": pair.pair_address, "dex_id": pair.dex_id, "pair_created_at": pair.pair_created_at.isoformat() if pair and pair.pair_created_at else None} if pair else None,
            "price_usd": snap.price_usd if snap else None,
            "liquidity_usd": snap.liquidity_usd if snap else None,
            "volume_24h": snap.volume_24h if snap else None,
            "price_change_1h": snap.price_change_1h if snap else None,
            "price_change_24h": snap.price_change_24h if snap else None,
            "observed_at": snap.observed_at.isoformat() if snap else None,
            "data_age_seconds": age,
            "stale": stale,
        })
    return {"items": out, "total": total, "limit": limit, "offset": offset}


def _snapshot_json(snap, *, now=None) -> dict:
    """Explicit projection. A raw ORM dict leaks internal columns."""
    if snap is None:
        return None
    now = now or datetime.now(UTC)
    observed = snap.observed_at if snap.observed_at.tzinfo else snap.observed_at.replace(tzinfo=UTC)
    age = (now - observed).total_seconds()
    return {
        "price_usd": snap.price_usd,
        "liquidity_usd": snap.liquidity_usd,
        "volume_5m": snap.volume_5m,
        "volume_1h": snap.volume_1h,
        "volume_24h": snap.volume_24h,
        "buys_5m": snap.buys_5m,
        "sells_5m": snap.sells_5m,
        "buys_1h": snap.buys_1h,
        "sells_1h": snap.sells_1h,
        "price_change_5m": snap.price_change_5m,
        "price_change_1h": snap.price_change_1h,
        "price_change_24h": snap.price_change_24h,
        "fdv": snap.fdv,
        "market_cap": snap.market_cap,
        "observed_at": snap.observed_at.isoformat() if snap.observed_at else None,
        "source": snap.source,
        "data_age_seconds": round(age, 3),
        "stale": age > settings.market_stale_after_seconds,
    }


def _pair_summary(pair) -> dict:
    return {
        "pair_address": pair.pair_address,
        "dex_id": pair.dex_id,
        "quote_token_address": pair.quote_token_address,
        "pair_created_at": pair.pair_created_at.isoformat() if pair.pair_created_at else None,
        "source": pair.source,
        "data_status": pair.data_status,
    }


def _risk_summary(risk) -> dict | None:
    if risk is None:
        return None
    return {
        "id": risk.id,
        "status": risk.status,
        "hard_reject": bool(risk.hard_reject),
        "risk_flags": risk.risk_flags,
        "coverage": risk.coverage,
        "rule_version": risk.rule_version,
        "evidence_refs": risk.evidence_refs,
        "assessed_at": risk.assessed_at.isoformat() if risk.assessed_at else None,
    }


def _find_token(db, mint: str) -> Token:
    t = db.query(Token).filter(Token.mint_address == mint).first()
    if not t:
        raise NotFoundError("token", mint)
    return t


def _latest_pair(db, token_id: str):
    return (
        db.query(TokenPair)
        .filter(TokenPair.token_id == token_id)
        .order_by(TokenPair.created_at.desc())
        .first()
    )


@router.get("/tokens/{mint}")
def get_token(mint: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    t = _find_token(db, mint)
    pair = _latest_pair(db, t.id)
    snap = latest_snapshot(db, pair.id) if pair else None
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.token_id == t.id)
        .order_by(RiskAssessment.assessed_at.desc())
        .first()
    )
    from app.services import onchain_service

    facts = onchain_service.get_cached_facts(db, t)
    return {
        "id": t.id,
        "chain": t.chain,
        "mint_address": t.mint_address,
        "symbol": t.symbol,
        "name": t.name,
        "decimals": t.decimals,
        "first_seen_at": t.first_seen_at.isoformat() if t.first_seen_at else None,
        "pair": _pair_summary(pair) if pair else None,
        "snapshot": _snapshot_json(snap),
        "risk": _risk_summary(risk),
        "onchain": facts.to_json() if facts else None,
        "explorer_url": f"https://solscan.io/token/{mint}",
    }


@router.get("/tokens/{mint}/pairs")
def get_token_pairs(mint: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    t = _find_token(db, mint)
    rows = (
        db.query(TokenPair).filter(TokenPair.token_id == t.id).order_by(TokenPair.created_at.desc()).all()
    )
    now = datetime.now(UTC)
    items = []
    for p in rows:
        snap = latest_snapshot(db, p.id)
        summary = _pair_summary(p)
        summary["snapshot"] = _snapshot_json(snap, now=now)
        items.append(summary)
    return {"mint_address": mint, "items": items, "total": len(items)}


@router.get("/tokens/{mint}/risk")
def get_token_risk(mint: str, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    """Latest risk assessment with its evidence, plus on-chain provenance."""
    t = _find_token(db, mint)
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.token_id == t.id)
        .order_by(RiskAssessment.assessed_at.desc())
        .first()
    )
    if risk is None:
        return {
            "mint_address": mint,
            "assessed": False,
            "note": "no analysis has run for this token yet",
            "risk": None,
            "onchain": None,
        }
    from app.services import onchain_service

    facts = onchain_service.get_cached_facts(db, t)
    return {
        "mint_address": mint,
        "assessed": True,
        "risk": _risk_summary(risk),
        "onchain": facts.to_json() if facts else None,
        "disclaimer": "UNKNOWN is not PASS. No claim of safety is implied.",
    }


@router.post("/tokens/{mint}/onchain/refresh")
def refresh_token_onchain(
    mint: str, db: Session = Depends(get_db), actor: str = Depends(require_operator)
):
    """Re-read authoritative on-chain state from Solana RPC."""
    from app.services import onchain_service

    t = _find_token(db, mint)
    facts = onchain_service.refresh_facts(db, t)
    return facts.to_json()


@router.get("/tokens/{mint}/candles")
def get_candles(
    mint: str,
    db: Session = Depends(get_db),
    timeframe: str = Query("M1"),
    limit: int = Query(200, le=1000),
    actor: str = Depends(current_actor),
):
    tf = (timeframe or "M1").upper()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise ValidationError(
            "unsupported timeframe {}; supported: {}".format(tf, ", ".join(SUPPORTED_TIMEFRAMES))
        )
    t = _find_token(db, mint)
    pair = _latest_pair(db, t.id)
    if not pair:
        return {
            "items": [],
            "timeframe": tf,
            "count": 0,
            "status": "UNAVAILABLE",
            "reason": "no pair registered for this token",
        }
    rows = (
        db.query(Candle)
        .filter(Candle.pair_id == pair.id, Candle.timeframe == tf)
        .order_by(Candle.open_time.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        # Missing data is reported as missing, never as an empty successful series.
        return {
            "items": [],
            "timeframe": tf,
            "count": 0,
            "status": "UNAVAILABLE",
            "reason": "no stored candles for this timeframe",
        }
    items = [
        {
            "time": c.open_time.isoformat(),
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "is_final": bool(c.is_final),
        }
        for c in reversed(rows)
    ]
    now = datetime.now(UTC)
    latest = items[-1]["time"]
    return {
        "items": items,
        "timeframe": tf,
        "count": len(items),
        "status": "OK",
        "latest_candle_at": latest,
        "data_age_seconds": round(
            (now - rows[0].open_time.replace(tzinfo=UTC)).total_seconds(), 3
        ),
    }


@router.post("/tokens/{mint}/analyze")
def analyze_token(
    mint: str,
    db: Session = Depends(get_db),
    use_ai: bool = False,
    refresh_onchain: bool = True,
    actor: str = Depends(require_operator),
):
    """Run the deterministic pipeline.

    Safety-critical inputs come from Solana RPC. `use_ai` only adds narrative;
    the model's opinion of authority state is never used as a risk input.
    """
    from app.services import onchain_service
    from app.services.analysis_service import run_analysis

    t = _find_token(db, mint)
    pair = _latest_pair(db, t.id)
    if not pair:
        raise NotFoundError("pair", mint)

    facts = onchain_service.get_or_fetch(db, t, allow_network=refresh_onchain)

    ai_context = None
    if use_ai:
        from app.services.agent_service import run_narrative_agents

        # All three narrative agents, not just onchain-risk. Output lands in
        # ai_summary, which nothing in scoring or the risk gate reads.
        ai_context = run_narrative_agents(db, t, pair, onchain=facts.to_json() if facts else None)

    run = run_analysis(db, t, pair, ai_context=ai_context, onchain_facts=facts)
    return {
        "run_id": run.id,
        "decision": run.decision,
        "score": run.score,
        "coverage": run.coverage,
        "reasons": run.reasons,
        "indicators": run.indicators,
        "onchain": facts.to_json() if facts else None,
        "ai_summary": run.ai_summary,
    }
