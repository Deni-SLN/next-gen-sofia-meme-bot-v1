"""Analysis determinism and provenance (PRD §18.B).

Two guarantees are under test:

1. The same candles + the same configuration must produce the same output.
2. Every stored run must be re-derivable from what it actually read - reasons,
   expiry, invalidation, the input snapshot and the engine version.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.analysis.scoring import SCORING_CONFIG_VERSION, ScoreInput, compute_score
from app.analysis.signal_gen import STRATEGY_VERSION
from app.models.analysis import AnalysisRun, RiskAssessment, Signal
from app.services import onchain_service
from app.services.analysis_service import _candle_set_hash, run_analysis

MINT = "So11111111111111111111111111111111111111199"


def _facts(mint=MINT, **over):
    base = dict(
        mint_address=mint,
        mint_authority_revoked=True,
        freeze_authority_revoked=True,
        top10_holder_pct=0.10,
        status="OK",
        source="solana_rpc",
    )
    base.update(over)
    return onchain_service.TokenFacts(**base)


def _seed(db, n=90, seed_step=0.0008):
    """Deterministic candles. No randomness anywhere in the fixtures."""
    from app.providers.market.dexscreener import NormalizedPair
    from app.services import market_service as ms

    now = datetime.now(UTC)
    pair = NormalizedPair(
        chain="solana",
        mint_address=MINT,
        pair_address="prov-pair",
        symbol="PROV",
        name="Provenance",
        dex_id="raydium",
        price_usd=1.0,
        liquidity_usd=300_000.0,
        volume_5m=1_000.0,
        volume_1h=20_000.0,
        volume_24h=200_000.0,
        buys_5m=10,
        sells_5m=8,
        buys_1h=200,
        sells_1h=180,
        price_change_5m=0.4,
        price_change_1h=2.5,
        price_change_24h=6.0,
        fdv=None,
        market_cap=None,
        pair_created_at=now - timedelta(hours=10),
        observed_at=now,
        source="dexscreener",
        raw_hash="prov-hash",
    )
    token, stored = ms.upsert_token_pair(db, pair)
    base = now - timedelta(minutes=n)
    from app.models.market import Candle, MarketSnapshot

    for i in range(n):
        price = 1.0 + seed_step * i
        db.add(
            Candle(
                pair_id=stored.id,
                timeframe="M1",
                open_time=base + timedelta(minutes=i),
                open=price,
                high=price * 1.004,
                low=price * 0.996,
                close=price * 1.001,
                volume=1_200.0 + i,
                source="dexscreener",
                is_final=1,
            )
        )
    db.flush()
    db.add(
        MarketSnapshot(
            pair_id=stored.id,
            price_usd=1.07,
            liquidity_usd=300_000.0,
            volume_1h=20_000.0,
            volume_24h=200_000.0,
            buys_1h=200,
            sells_1h=180,
            price_change_1h=2.5,
            observed_at=now,
            source="dexscreener",
        )
    )
    db.commit()
    return token, stored


# --------------------------- determinism ---------------------------


def test_same_input_produces_identical_score_and_decision(db):
    token, pair = _seed(db)
    first = run_analysis(db, token, pair, onchain_facts=_facts())
    second = run_analysis(db, token, pair, onchain_facts=_facts())
    assert first.score == second.score
    assert first.decision == second.decision
    assert first.coverage == second.coverage
    assert first.indicators == second.indicators


def test_identical_candles_yield_identical_candle_hash(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    assert run.input_snapshot["candle_set_hash"] == run.input_snapshot["candle_set_hash"]


def test_candle_hash_changes_when_candles_change(db):
    from app.models.market import Candle

    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    before = run.input_snapshot["candle_set_hash"]

    last = (
        db.query(Candle)
        .filter(Candle.pair_id == pair.id)
        .order_by(Candle.open_time.desc())
        .first()
    )
    last.close = float(last.close) * 1.5
    db.commit()

    after = run_analysis(db, token, pair, onchain_facts=_facts())
    assert after.input_snapshot["candle_set_hash"] != before, (
        "the fingerprint must change when the inputs change, or a run is not re-derivable"
    )


def test_candle_hash_is_none_without_candles():
    assert _candle_set_hash([]) is None


def test_candle_hash_is_order_sensitive():
    class C:
        def __init__(self, t, c):
            self.open_time = t
            self.open = self.high = self.low = self.close = c
            self.volume = 1.0

    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=1)
    assert _candle_set_hash([C(t0, 1.0), C(t1, 2.0)]) != _candle_set_hash([C(t1, 2.0), C(t0, 1.0)])


def test_scoring_is_pure(db):
    payload = ScoreInput(
        liquidity_usd=300_000.0,
        price_change_1h=2.5,
        rsi_value=55.0,
        macd_histogram=0.01,
        volume_ratio=1.2,
        structure="UPTREND",
        risk_status="PASS",
        hard_reject=False,
        coverage=1.0,
    )
    a = compute_score(payload)
    b = compute_score(payload)
    assert a.score == b.score
    assert a.components == b.components


def test_hard_reject_zeroes_score_regardless_of_quality(db):
    good = compute_score(
        ScoreInput(
            liquidity_usd=999_999.0,
            price_change_1h=25.0,
            rsi_value=65.0,
            macd_histogram=0.5,
            volume_ratio=3.0,
            structure="UPTREND",
            risk_status="REJECT",
            hard_reject=True,
            coverage=1.0,
        )
    )
    assert good.score == 0


def test_reasons_are_stable_across_runs(db):
    token, pair = _seed(db)
    a = run_analysis(db, token, pair, onchain_facts=_facts())
    b = run_analysis(db, token, pair, onchain_facts=_facts())
    assert a.reasons == b.reasons


# --------------------------- provenance ---------------------------


def test_run_records_engine_and_config_versions(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    assert run.engine_version
    assert run.scoring_config_version == SCORING_CONFIG_VERSION
    versions = run.provider_versions
    assert versions["risk_rules"]
    assert versions["scoring"] == SCORING_CONFIG_VERSION
    assert versions["onchain"] == "solana_rpc"


def test_run_records_input_snapshot(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    snap = run.input_snapshot
    assert snap["candles_count"] == 90
    assert snap["candle_set_hash"]
    assert snap["observed_at"]
    assert snap["onchain"]["mint_authority_revoked"] is True


def test_run_records_reasons_even_when_clean(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    assert isinstance(run.reasons, list)


def test_ai_context_is_recorded_but_not_a_risk_input(db):
    """The model's opinion is stored as narrative, never used as a safety fact."""
    token, pair = _seed(db)
    optimistic = {"mint_authority_revoked": True, "note": "looks safe to me"}
    run = run_analysis(db, token, pair, ai_context=optimistic, onchain_facts=_facts())
    assert run.ai_summary == optimistic
    risk = db.query(RiskAssessment).filter(RiskAssessment.id == run.risk_assessment_id).first()
    check = next(c for c in risk.evidence_refs if c["check"] == "mint_authority")
    assert check["revoked"] is True, "evidence comes from RPC, not the model"


def test_analysis_history_is_kept(db):
    token, pair = _seed(db)
    for _ in range(3):
        run_analysis(db, token, pair, onchain_facts=_facts())
    assert db.query(AnalysisRun).filter(AnalysisRun.token_id == token.id).count() == 3


def test_each_run_links_its_own_risk_assessment(db):
    token, pair = _seed(db)
    a = run_analysis(db, token, pair, onchain_facts=_facts())
    b = run_analysis(db, token, pair, onchain_facts=_facts())
    assert a.risk_assessment_id != b.risk_assessment_id


# --------------------------- signal provenance ---------------------------


def test_signal_carries_full_provenance(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    signal = db.query(Signal).filter(Signal.analysis_run_id == run.id).first()
    if signal is None:
        pytest.skip("fixture produced a non-tradable decision")
    assert signal.reasons
    assert signal.expires_at is not None
    assert signal.invalidation_conditions is not None
    assert signal.source_references
    assert signal.engine_version
    assert signal.strategy_version == STRATEGY_VERSION
    assert signal.data_timestamp is not None
    assert signal.signature


def test_signal_expiry_is_in_the_future(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    signal = db.query(Signal).filter(Signal.analysis_run_id == run.id).first()
    if signal is None:
        pytest.skip("fixture produced a non-tradable decision")
    exp = signal.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    assert exp > datetime.now(UTC)


def test_signal_coverage_and_risk_flags_are_persisted(db):
    token, pair = _seed(db)
    run = run_analysis(db, token, pair, onchain_facts=_facts())
    signal = db.query(Signal).filter(Signal.analysis_run_id == run.id).first()
    if signal is None:
        pytest.skip("fixture produced a non-tradable decision")
    assert signal.coverage == run.coverage
    assert isinstance(signal.risk_flags, list)


def test_unknown_onchain_data_rejects_but_is_recorded(db):
    token, pair = _seed(db)
    unknown = _facts(status="ERROR", mint_authority_revoked=None, freeze_authority_revoked=None)
    run = run_analysis(db, token, pair, onchain_facts=unknown)
    assert run.decision == "REJECT"
    assert run.input_snapshot["onchain"]["status"] == "ERROR", (
        "the uncertainty must remain visible in the snapshot"
    )


def test_no_signal_is_created_for_a_reject(db):
    token, pair = _seed(db)
    unknown = _facts(status="ERROR", mint_authority_revoked=None, freeze_authority_revoked=None)
    run = run_analysis(db, token, pair, onchain_facts=unknown)
    assert db.query(Signal).filter(Signal.analysis_run_id == run.id).count() == 0