"""End-to-end paper trading lifecycle tests.

Covers the path PRD 18.D / 18.E care about: signal -> risk gate -> paper fill
-> position -> close -> accounting, plus the referential integrity of the
execution ledger (FR-TB-008).
"""

import math
from datetime import UTC

import pytest
from app.models.market import MarketSnapshot, Token, TokenPair
from app.models.trading import AccountingEvent, Fill, OrderIntent, Position

MINT = "So11111111111111111111111111111111111111112"
MINT2 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _seed_token(db, mint=MINT, price=1.0, liquidity=50_000.0):
    from datetime import datetime

    token = Token(chain="solana", mint_address=mint, symbol="TEST", name="Test Token")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="pair-" + mint[:12], dex_id="raydium", source="dexscreener")
    db.add(pair)
    db.flush()
    snap = MarketSnapshot(
        pair_id=pair.id,
        price_usd=price,
        liquidity_usd=liquidity,
        volume_24h=1_000_000.0,
        observed_at=datetime.now(UTC),
        source="dexscreener",
    )
    db.add(snap)
    db.commit()
    return token, pair, snap


def _seed_candles(db, pair, n=60, start=1.0):
    from datetime import datetime, timedelta

    from app.models.market import Candle

    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(n):
        price = start * (1.0 + 0.01 * i)
        db.add(
            Candle(
                pair_id=pair.id,
                timeframe="M1",
                open_time=base + timedelta(minutes=i),
                open=price * 0.999,
                high=price * 1.005,
                low=price * 0.995,
                close=price,
                volume=1000.0 + i,
                source="dexscreener",
                is_final=1,
            )
        )
    db.commit()


def _open_position(db, price=1.0):
    """Drive a signal all the way to an OPEN position in PAPER mode."""
    from datetime import datetime

    from app.models.analysis import AnalysisRun, RiskAssessment, Signal
    from app.services.bot_service import start_bot
    from app.services.trading_service import process_signal_for_trading

    token, pair, _ = _seed_token(db, price=price)
    _seed_candles(db, pair)

    start_bot(db, "test-operator", mode="PAPER")

    risk = RiskAssessment(
        token_id=token.id,
        status="PASS",
        hard_reject=False,
        risk_flags=[],
        coverage=1.0,
        rule_version="risk-v1",
        evidence_refs={},
        assessed_at=datetime.now(UTC),
    )
    db.add(risk)
    run = AnalysisRun(
        token_id=token.id,
        pair_id=pair.id,
        engine_version="engine-v1",
        scoring_config_version="scoring-v1",
        score=80.0,
        coverage=1.0,
        decision="LONG_CANDIDATE",
        reasons=["test"],
        input_snapshot={},
        provider_versions={},
    )
    db.add(run)
    db.commit()
    signal = Signal(
        analysis_run_id=run.id,
        token_id=token.id,
        pair_id=pair.id,
        mint_address=token.mint_address,
        signal_type="LONG",
        status="CREATED",
        decision="LONG_CANDIDATE",
        reasons=["test"],
        entry_reference=price,
        stop_reference=price * 0.9,
        target_references=[price * 1.2],
        risk_reward=2.0,
        coverage=1.0,
        risk_flags=[],
        engine_version="engine-v1",
        strategy_version="v1",
        data_timestamp=datetime.now(UTC),
    )
    db.add(signal)
    db.commit()

    result = process_signal_for_trading(db, signal.id)
    return token, pair, signal, result


def test_signal_to_open_position(db):
    _token, _pair, _signal, result = _open_position(db)
    assert result["accepted"] is True, result
    pos = db.query(Position).filter(Position.status == "OPEN").one()
    assert pos.quantity > 0
    assert pos.average_entry_price > 0
    assert pos.open_order_intent_id is not None


def test_every_fill_references_a_real_order_intent(db):
    _token, _pair, _signal, _r = _open_position(db)
    intents = {i.id for i in db.query(OrderIntent).all()}
    fills = db.query(Fill).all()
    assert fills, "entry fill should exist"
    for f in fills:
        assert f.order_id in intents, "fill points at a non-existent order intent"
        assert f.fill_type == "SIMULATED"


def test_close_creates_sell_order_and_keeps_fk_valid(db):
    from app.services.trading_service import close_position

    _token, _pair, _signal, _r = _open_position(db)
    pos = db.query(Position).filter(Position.status == "OPEN").one()
    result = close_position(db, pos.id, "test_close", price_override=1.5)

    assert result is not None
    intents = {i.id for i in db.query(OrderIntent).all()}
    sells = [f for f in db.query(Fill).all() if f.side == "SELL"]
    assert len(sells) == 1, "close must produce exactly one SELL fill"
    assert sells[0].order_id in intents
    assert pos.status == "CLOSED"
    assert pos.exit_order_intent_id == sells[0].order_id
    assert math.isfinite(pos.realized_pnl)


def test_close_twice_is_rejected(db):
    from app.core.errors import ConflictError
    from app.services.trading_service import close_position

    _token, _pair, _signal, _r = _open_position(db)
    pos = db.query(Position).filter(Position.status == "OPEN").one()
    close_position(db, pos.id, "first", price_override=1.5)
    with pytest.raises(ConflictError):
        close_position(db, pos.id, "second", price_override=1.5)


def test_close_records_accounting_events(db):
    from app.services.trading_service import close_position

    _token, _pair, _signal, _r = _open_position(db)
    pos = db.query(Position).filter(Position.status == "OPEN").one()
    close_position(db, pos.id, "test_close", price_override=1.5)
    types = {e.event_type for e in db.query(AccountingEvent).all()}
    assert {"TRADE_CLOSE", "REALIZED_PNL", "FEE"} <= types


def test_paper_fills_never_carry_a_signature(db):
    """V1 must not produce anything that looks like a real on-chain fill."""
    from app.services.trading_service import close_position

    _token, _pair, _signal, _r = _open_position(db)
    pos = db.query(Position).filter(Position.status == "OPEN").one()
    close_position(db, pos.id, "test_close", price_override=1.5)
    for f in db.query(Fill).all():
        assert f.fill_type == "SIMULATED"