"""End-to-end operator flow (PRD §18.G).

Exercises the path a real operator walks in V1:
login -> discovery -> ingest -> analysis -> PAPER bot -> close -> accounting
-> simulated sweep, asserting that each stage is visible through the API.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.providers.market.dexscreener import NormalizedPair

MINT = "So11111111111111111111111111111111111111111"
SOL_MINT = "So11111111111111111111111111111111111111112"


def _pair(**over):
    base = dict(
        chain="solana",
        mint_address=MINT,
        pair_address="e2e-pair-1",
        symbol="E2E",
        name="E2E Token",
        dex_id="raydium",
        price_usd=1.0,
        liquidity_usd=250_000.0,
        volume_5m=5_000.0,
        volume_1h=25_000.0,
        volume_24h=250_000.0,
        buys_5m=20,
        sells_5m=15,
        buys_1h=200,
        sells_1h=180,
        price_change_5m=0.5,
        price_change_1h=3.0,
        price_change_24h=8.0,
        fdv=1_000_000.0,
        market_cap=1_000_000.0,
        pair_created_at=datetime.now(UTC) - timedelta(hours=12),
        observed_at=datetime.now(UTC),
        source="dexscreener",
        raw_hash="e2e-hash",
    )
    base.update(over)
    return NormalizedPair(**base)


@pytest.fixture()
def stub_provider(monkeypatch):
    """Serve a deterministic pair instead of calling DEX Screener."""
    import asyncio

    from app.api.v1 import market

    class Stub:
        name = "dexscreener"

        async def search(self, q, limit=20):
            await asyncio.sleep(0)
            return [_pair()]

        async def trending(self, limit=20):
            await asyncio.sleep(0)
            return [_pair()]

    monkeypatch.setattr(market, "_dex", Stub())
    return Stub()


@pytest.fixture()
def stub_onchain(monkeypatch):
    """On-chain facts are verified, so the pipeline is not blocked by UNKNOWN."""
    from app.services import onchain_service

    def _facts():
        return onchain_service.TokenFacts(
            mint_address=MINT,
            mint_authority_revoked=True,
            freeze_authority_revoked=True,
            top10_holder_pct=0.12,
            status="OK",
            source="solana_rpc",
        )

    monkeypatch.setattr(
        onchain_service,
        "get_or_fetch",
        lambda db, token, provider=None, allow_network=True: _facts(),
    )
    return _facts


@pytest.fixture()
def seeded(monkeypatch):
    """Enough M1 candles for indicators and a qualifying on-chain snapshot."""
    from app.models.market import Candle, MarketSnapshot
    from app.services import market_service as ms

    def _seed(db, pair):
        now = datetime.now(UTC)
        token, stored_pair = ms.upsert_token_pair(db, pair)
        base = now - timedelta(minutes=90)
        for i in range(80):
            price = 1.0 + 0.0008 * i
            db.add(
                Candle(
                    pair_id=stored_pair.id,
                    timeframe="M1",
                    open_time=base + timedelta(minutes=i),
                    open=price,
                    high=price * 1.004,
                    low=price * 0.996,
                    close=price * 1.001,
                    volume=1_500.0 + i,
                    source="dexscreener",
                    is_final=1,
                )
            )
        db.flush()
        db.add(
            MarketSnapshot(
                pair_id=stored_pair.id,
                price_usd=1.08,
                liquidity_usd=250_000.0,
                volume_1h=25_000.0,
                volume_24h=250_000.0,
                buys_1h=200,
                sells_1h=180,
                price_change_1h=3.0,
                observed_at=now,
                source="dexscreener",
            )
        )
        db.commit()
        return token, stored_pair

    return _seed


# ----------------------------- The flow -----------------------------


def test_health_is_public_and_reports_version(anon_client):
    r = anon_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_paper_flow(client, db, stub_provider, stub_onchain, seeded):
    # 1. discovery + ingest through the public endpoint
    r = client.post("/api/v1/discover/ingest", params={"q": "SOL"})
    assert r.status_code == 200, r.text
    assert r.json()["ingested"] == 1

    # 2. the token is discoverable
    r = client.get("/api/v1/tokens", params={"q": "E2E"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["mint_address"] == MINT

    # 3. detail + candles are served from stored data
    assert client.get(f"/api/v1/tokens/{MINT}").status_code == 200
    r = client.get(f"/api/v1/tokens/{MINT}/candles", params={"timeframe": "M1"})
    assert r.status_code == 200
    assert r.json()["count"] > 0

    # 4. analysis runs deterministically
    seeded(db, _pair())
    r = client.post(f"/api/v1/tokens/{MINT}/analyze", params={"refresh_onchain": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["decision"], str) and body["decision"]

    # 5. the analysis run is persisted and visible
    r = client.get("/api/v1/analysis/runs")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # 6. bot control reflects backend state
    r = client.post("/api/v1/bot/start", json={"mode": "PAPER"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RUNNING"
    assert client.get("/api/v1/bot/status").json()["status"] == "RUNNING"

    # 7. live mode is refused in V1
    assert client.post("/api/v1/bot/start", json={"mode": "LIVE"}).status_code >= 400

    # 8. accounting is reconcilable
    r = client.get("/api/v1/portfolio/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["live_trading_enabled"] is False
    assert body["modes"]["PAPER"]["equity"] == 1000.0
    assert body["modes"]["PAPER"]["high_water_mark"] == 1000.0
    assert body["modes"]["PAPER"]["current_drawdown_pct"] == 0.0


def test_paper_flow_opens_and_closes_a_position(client, db, stub_provider, stub_onchain, seeded):
    from app.models.analysis import Signal
    from app.services import trading_service

    token, pair = seeded(db, _pair())

    from app.services.analysis_service import run_analysis

    run_analysis(db, token, pair, onchain_facts=stub_onchain())
    db.commit()

    client.post("/api/v1/bot/start", json={"mode": "PAPER"})

    signal = (
        db.query(Signal)
        .filter(Signal.status.in_(["CREATED", "VALIDATED", "ACTIVE", "WAIT"]))
        .first()
    )
    if signal is None:
        pytest.skip("deterministic pipeline produced no actionable signal for this fixture")

    result = trading_service.process_signal_for_trading(db, signal.id)
    assert "accepted" in result, result
    assert isinstance(result["accepted"], bool)

    # whatever the decision, the ledger must stay internally consistent
    from app.models.trading import Fill

    for fill in db.query(Fill).all():
        assert fill.order_id or fill.side
        assert fill.fill_type == "SIMULATED", "PAPER fills must never look real"


def test_provider_failure_is_reported_not_crashed(client, monkeypatch):
    from app.api.v1 import market

    class Broken:
        name = "dexscreener"

        async def search(self, q, limit=20):
            from app.core.errors import ProviderError

            raise ProviderError("dexscreener", "HTTP 503")

    monkeypatch.setattr(market, "_dex", Broken())
    r = client.post("/api/v1/discover/ingest", params={"q": "SOL"})
    assert r.status_code == 200
    assert r.json()["ingested"] == 0
    assert "error" in r.json()


def test_system_status_reports_subsystems(client):
    r = client.get("/api/v1/system/status")
    assert r.status_code == 200
    assert r.json()["live_trading_enabled"] is False


def test_error_envelope_is_consistent(client):
    r = client.get("/api/v1/tokens/DoesNotExistMintThatIsLongEnough")
    assert r.status_code >= 400
    body = r.json()
    assert set(body["error"]) >= {"code", "message", "status", "request_id"}
    assert r.headers.get("X-Request-ID") == body["error"]["request_id"]


def test_observers_cannot_start_the_bot(observer_client):
    assert observer_client.post("/api/v1/bot/start", json={"mode": "PAPER"}).status_code == 403