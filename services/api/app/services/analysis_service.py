"""Analysis pipeline: candles+snapshot -> indicators -> risk -> score -> signal (FR-AE-001..008)."""

import hashlib
import math
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.analysis.indicators import (
    atr,
    ema,
    macd,
    market_structure,
    rsi,
    support_resistance,
    volume_ratio,
)
from app.analysis.risk import RiskInput, assess_risk
from app.analysis.scoring import SCORING_CONFIG_VERSION, ScoreInput, compute_score
from app.analysis.signal_gen import (
    STRATEGY_VERSION,
    compute_signature,
    generate_signal_plan,
    signal_expiry,
)
from app.core.config import settings
from app.models.analysis import AnalysisRun, RiskAssessment, Signal
from app.models.market import Candle, MarketSnapshot, Token, TokenPair
from app.models.ops import SettingEntry
from app.services import onchain_service


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _candle_set_hash(candles: list) -> str | None:
    """Stable fingerprint of the exact candles an analysis ran on.

    Reproducibility (PRD §10.4): an analysis run must be re-derivable from what
    it actually read, not just from a candle count.
    """
    if not candles:
        return None
    h = hashlib.sha256()
    for c in candles:
        stamp = c.open_time.isoformat() if c.open_time else ""
        h.update(
            f"{stamp}|{c.open}|{c.high}|{c.low}|{c.close}|{c.volume};".encode()
        )
    return h.hexdigest()[:32]


def _nearest_below(levels: list[float] | None, price: float | None) -> float | None:
    """Highest support strictly below the price.

    Using levels[-1] picks the *highest* support, which is usually above the
    entry price and therefore always discarded by the stop-placement guard,
    silently reducing every stop to the ATR fallback.
    """
    if not levels or price is None:
        return None
    below = [x for x in levels if x is not None and _finite(x) and x < price]
    return max(below) if below else None


def _nearest_above(levels: list[float] | None, price: float | None) -> float | None:
    """Lowest resistance strictly above the price."""
    if not levels or price is None:
        return None
    above = [x for x in levels if x is not None and _finite(x) and x > price]
    return min(above) if above else None


def get_risk_rules(db: Session) -> dict:
    row = db.query(SettingEntry).filter(SettingEntry.key == "risk_rules").first()
    return row.value_json if row and isinstance(row.value_json, dict) else {}


def run_analysis(
    db: Session,
    token: Token,
    pair: TokenPair,
    ai_context: dict | None = None,
    onchain_facts=None,
) -> AnalysisRun:
    """Run the deterministic analysis pipeline and persist a Signal when applicable.

    `ai_context` is narrative only. Safety-critical risk inputs (mint/freeze
    authority, holder concentration) come from `onchain_facts`, read from
    Solana RPC. An LLM can never turn an unverified check into a PASS
    (FR-AE-004: UNKNOWN is not PASS).
    """
    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.pair_id == pair.id)
        .order_by(MarketSnapshot.observed_at.desc())
        .limit(200)
        .all()
    )
    latest = snaps[0] if snaps else None

    candles = (
        db.query(Candle)
        .filter(Candle.pair_id == pair.id, Candle.timeframe == "M1")
        .order_by(Candle.open_time.desc())
        .limit(400)
        .all()
    )
    candles = list(reversed(candles))
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    vols = [c.volume for c in candles]

    rsi_val = rsi(closes) if len(closes) >= 15 else (rsi(closes, max(3, len(closes) - 1)) if len(closes) >= 5 else None)
    macd_res = macd(closes) if len(closes) >= 35 else macd(closes, 5, 10, 5)
    atr_val = atr(highs, lows, closes) if len(closes) >= 15 else (atr(highs, lows, closes, max(3, len(closes) - 1)) if len(closes) >= 5 else None)
    ema9 = ema(closes, 9) if len(closes) >= 9 else None
    ema21 = ema(closes, 21) if len(closes) >= 21 else None
    vol_ratio = (
        volume_ratio(vols)
        if len(vols) >= 21
        else (volume_ratio(vols, max(3, len(vols) - 1)) if len(vols) >= 5 else None)
    )
    if vol_ratio is None and latest and _finite(latest.volume_5m) and _finite(latest.volume_1h) and latest.volume_1h > 0:
        avg_5m = latest.volume_1h / 12.0
        vol_ratio = latest.volume_5m / avg_5m if avg_5m > 0 else None
    structure = market_structure(closes, highs, lows) if len(closes) >= 10 else (market_structure(closes, highs, lows, lookback=1) if len(closes) >= 5 else None)
    sr = support_resistance(highs, lows) if len(closes) >= 10 else (support_resistance(highs, lows, lookback=1) if len(closes) >= 5 else None)

    price = latest.price_usd if latest else None
    liq = latest.liquidity_usd if latest else None

    pool_age_min = None
    if pair.pair_created_at:
        created = pair.pair_created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        pool_age_min = (datetime.now(UTC) - created).total_seconds() / 60.0

    rules = get_risk_rules(db)
    # Safety-critical inputs come from the chain, never from the model.
    if onchain_facts is None:
        onchain_facts = onchain_service.get_or_fetch(db, token)
    chain = onchain_service.evidence_for_risk(onchain_facts)
    risk = assess_risk(
        RiskInput(
            price_usd=price,
            liquidity_usd=liq,
            pool_age_minutes=pool_age_min,
            buys_1h=latest.buys_1h if latest else None,
            sells_1h=latest.sells_1h if latest else None,
            mint_authority_revoked=chain["mint_authority_revoked"],
            freeze_authority_revoked=chain["freeze_authority_revoked"],
            top10_holder_pct=chain["top10_holder_pct"],
        ),
        rules=rules,
    )

    score = compute_score(
        ScoreInput(
            liquidity_usd=liq,
            price_change_1h=latest.price_change_1h if latest else None,
            rsi_value=rsi_val,
            macd_histogram=macd_res.histogram if macd_res else None,
            volume_ratio=vol_ratio,
            structure=structure.structure if structure else None,
            risk_status=risk.status,
            hard_reject=risk.hard_reject,
            coverage=risk.coverage,
        )
    )

    plan = generate_signal_plan(
        price=price,
        atr_value=atr_val,
        support=_nearest_below(sr.supports if sr else None, price),
        resistance=_nearest_above(sr.resistances if sr else None, price),
        structure=structure.structure if structure else None,
        risk=risk,
        score=score,
        liquidity_usd=liq,
    )

    risk_row = RiskAssessment(
        token_id=token.id,
        status=risk.status,
        hard_reject=1 if risk.hard_reject else 0,
        risk_flags=risk.risk_flags,
        coverage=risk.coverage,
        rule_version=risk.rule_version,
        evidence_refs=risk.evidence_refs,
        assessed_at=risk.assessed_at,
    )
    db.add(risk_row)
    db.flush()

    input_snapshot = {
        "price_usd": price,
        "liquidity_usd": liq,
        "volume_1h": latest.volume_1h if latest else None,
        "buys_1h": latest.buys_1h if latest else None,
        "sells_1h": latest.sells_1h if latest else None,
        "price_change_1h": latest.price_change_1h if latest else None,
        "snapshot_id": latest.id if latest else None,
        "candle_set_hash": _candle_set_hash(candles),
        "candles_count": len(candles),
        "observed_at": latest.observed_at.isoformat() if latest else None,
        "source": latest.source if latest else None,
        "onchain": onchain_facts.to_json() if onchain_facts else None,
    }
    run = AnalysisRun(
        token_id=token.id,
        pair_id=pair.id,
        engine_version=settings.engine_version,
        scoring_config_version=SCORING_CONFIG_VERSION,
        input_snapshot=input_snapshot,
        risk_assessment_id=risk_row.id,
        score=score.score,
        coverage=risk.coverage,
        decision=plan.decision,
        reasons=plan.reasons,
        indicators={
            "rsi": rsi_val,
            "macd": macd_res.__dict__ if macd_res else None,
            "atr": atr_val,
            "ema9": ema9,
            "ema21": ema21,
            "volume_ratio": vol_ratio,
            "structure": structure.__dict__ if structure else None,
            "support": sr.supports if sr else None,
            "resistance": sr.resistances if sr else None,
        },
        provider_versions={
            "market": latest.source if latest else None,
            "onchain": (onchain_facts.source if onchain_facts else None),
            "risk_rules": risk.rule_version,
            "scoring": SCORING_CONFIG_VERSION,
        },
        ai_summary=ai_context,
    )
    db.add(run)
    db.flush()

    if plan.decision in ("LONG_CANDIDATE", "BEARISH_BIAS"):
        now = datetime.now(UTC)
        sig_payload = {"run_id": run.id, "mint": token.mint_address, "decision": plan.decision, "ts": now.isoformat()}
        signal = Signal(
            analysis_run_id=run.id,
            token_id=token.id,
            pair_id=pair.id,
            mint_address=token.mint_address,
            signal_type=plan.decision,
            status="CREATED",
            engine_version=settings.engine_version,
            strategy_version=STRATEGY_VERSION,
            decision=plan.decision,
            reasons=plan.reasons,
            entry_reference=plan.entry_reference,
            stop_reference=plan.stop_reference,
            target_references=plan.target_references,
            fee_assumptions=plan.fee_assumptions,
            slippage_assumption=plan.slippage_assumption,
            risk_reward=plan.risk_reward,
            invalidation_conditions=plan.invalidation_conditions,
            data_timestamp=latest.observed_at if latest else now,
            coverage=risk.coverage,
            risk_flags=risk.risk_flags,
            source_references=[{"pair": pair.pair_address, "dex": pair.dex_id}],
            signature=compute_signature(sig_payload),
            expires_at=signal_expiry(now, 30),
        )
        db.add(signal)
    db.commit()
    db.refresh(run)
    return run

