"""Market data provider guarantees (PRD §18.A).

The contract under test: a degraded or lying provider must never be able to
silently turn "unknown" into "zero" or drop a whole batch on one bad row.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.errors import ProviderError
from app.providers.market.dexscreener import DexScreenerProvider, NormalizedPair, SchemaChangeError
from app.services import market_service as ms

# ----------------------------- Response builders -----------------------------


def _payload(**over):
    base = {
        "chainId": "solana",
        "pairAddress": "pair-1",
        "baseToken": {"address": "Mint1111111111111111111111111111111111111", "symbol": "T", "decimals": 9},
        "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
        "dexId": "raydium",
        "priceUsd": "1.0",
        "liquidity": {"usd": 50000},
        "volume": {"m5": "1000", "h1": "5000", "h24": "20000"},
        "txns": {"m5": {"buys": 5, "sells": 4}, "h1": {"buys": 50, "sells": 40}},
        "priceChange": {"m5": 1, "h1": 2, "h24": 3},
        "pairCreatedAt": 1_700_000_000_000,
    }
    base.update(over)
    return base


class FakeResp:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"data": []}
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        if self._payload is _MALFORMED:
            raise ValueError("not json")
        return self._payload


_MALFORMED = object()


def _provider(responses):
    """Provider whose client replays `responses` in order."""
    p = DexScreenerProvider(base_url="http://test.invalid", rate_per_min=1_000_000)
    seq = list(responses)
    calls = []

    class FakeClient:
        is_closed = False

        async def get(self, path, params=None):
            calls.append((path, params))
            return seq.pop(0) if len(seq) > 1 else seq[0]

        async def aclose(self):
            return None

    p._client = FakeClient()
    p._calls = calls
    return p


# ----------------------------- Normalisation -----------------------------


def test_normalize_extracts_identity_and_decimals():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    out = asyncio.run(p.token_pairs("Mint1111111111111111111111111111111111111"))
    assert len(out) == 1
    pair = out[0]
    assert pair.chain == "solana"
    assert pair.pair_address == "pair-1"
    assert pair.dex_id == "raydium"
    assert pair.decimals == 9
    assert pair.quote_token_address == "So11111111111111111111111111111111111111112"
    assert pair.price_usd == 1.0


def test_non_solana_pair_is_skipped():
    p = _provider([FakeResp(payload={"pairs": [_payload(chainId="ethereum")]})])
    assert asyncio.run(p.token_pairs("x")) == []


def test_unusable_row_does_not_kill_the_batch():
    """One unusable record is skipped; the good one still lands."""
    rows = [{"chainId": "solana", "pairAddress": "broken"}, _payload(pairAddress="good")]
    p = _provider([FakeResp(payload={"pairs": rows})])
    out = asyncio.run(p.token_pairs("m"))
    assert [x.pair_address for x in out] == ["good"]


def test_schema_change_on_a_row_is_reported_and_skipped():
    rows = [{"chainId": "solana", "pairAddress": "x"}, _payload(pairAddress="good")]
    p = _provider([FakeResp(payload={"pairs": rows})])
    out = asyncio.run(p.token_pairs("m"))
    assert [x.pair_address for x in out] == ["good"]


def test_missing_required_key_raises_schema_change():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    with pytest.raises(SchemaChangeError):
        p._check_schema({"chainId": "solana"})


def test_check_schema_passes_for_complete_payload():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    p._check_schema(_payload())  # must not raise


# ----------------------------- HTTP failure modes -----------------------------


@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_server_and_rate_limit_errors_raise_provider_error(status):
    p = _provider([FakeResp(status=status, text="err")])
    p._cache.clear()
    with pytest.raises(ProviderError):
        asyncio.run(p._fetch_with_retry("/latest/dex/tokens/x", None, "tokens", max_retries=0))


def test_retry_after_header_is_respected(monkeypatch):
    slept = []
    p = _provider([FakeResp(status=429, text="slow down", headers={"retry-after": "0.01"})])

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    with pytest.raises(ProviderError):
        asyncio.run(p._fetch_with_retry("/x", None, "tokens", max_retries=2))
    assert any(abs(d - 0.01) < 1e-6 for d in slept), slept


def test_transport_timeout_is_retried_then_raised():
    attempts = {"n": 0}

    class TimeoutClient:
        is_closed = False

        async def get(self, *a, **k):
            attempts["n"] += 1
            raise httpx.TimeoutException("timeout")

    p = _provider([FakeResp()])
    p._client = TimeoutClient()

    async def no_sleep(_):
        return None

    original = asyncio.sleep
    asyncio.sleep = no_sleep
    try:
        with pytest.raises(ProviderError):
            asyncio.run(p._fetch_with_retry("/x", None, "tokens", max_retries=2))
    finally:
        asyncio.sleep = original
    assert attempts["n"] == 3


def test_malformed_json_is_not_swallowed():
    p = _provider([FakeResp(payload=_MALFORMED)])
    p._cache.clear()
    with pytest.raises(ProviderError):
        asyncio.run(p._fetch_with_retry("/x", None, "tokens", max_retries=0))


def test_transient_failure_then_success(monkeypatch):
    p = _provider([FakeResp(status=503, text="boom"), FakeResp(payload={"pairs": [_payload()]})])

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    p._cache.clear()
    data = asyncio.run(p._fetch_with_retry("/x", None, "tokens", max_retries=1))
    assert "pairs" in data


# ----------------------------- Cache & dedup -----------------------------


def test_second_identical_request_is_served_from_cache():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    p._cache.clear()
    asyncio.run(p.token_pairs("m"))
    before = len(p._calls)
    asyncio.run(p.token_pairs("m"))
    assert len(p._calls) == before, "cache must absorb the repeat request"


def test_different_mint_is_not_served_from_the_other_cache_entry():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    p._cache.clear()
    asyncio.run(p.token_pairs("mint-a"))
    before = len(p._calls)
    asyncio.run(p.token_pairs("mint-b"))
    assert len(p._calls) == before + 1


def test_concurrent_identical_requests_are_deduplicated():
    p = _provider([FakeResp(payload={"pairs": [_payload()]})])
    p._cache.clear()
    results = []

    async def run():
        results.extend(await asyncio.gather(p.token_pairs("m"), p.token_pairs("m"), p.token_pairs("m")))

    asyncio.run(run())
    assert len(results[0]) == 1
    assert len(results[1]) == 1


# ----------------------------- Volume delta -----------------------------


def _pair(**over):
    base = dict(
        chain="solana",
        mint_address="Mint1111111111111111111111111111111111111",
        pair_address="pair-1",
        symbol="T",
        name="T",
        dex_id="raydium",
        price_usd=1.0,
        liquidity_usd=50_000.0,
        volume_5m=1000.0,
        volume_1h=5000.0,
        volume_24h=20_000.0,
        buys_5m=5,
        sells_5m=4,
        buys_1h=50,
        sells_1h=40,
        price_change_5m=1.0,
        price_change_1h=2.0,
        price_change_24h=3.0,
        fdv=None,
        market_cap=None,
        pair_created_at=datetime.now(UTC) - timedelta(hours=5),
        observed_at=datetime.now(UTC),
        source="dexscreener",
        raw_hash="h1",
    )
    base.update(over)
    return NormalizedPair(**base)


def test_first_reading_has_no_delta_not_zero():
    assert ms._volume_delta(None, 1000.0, datetime.now(UTC)) is None


def test_missing_cumulative_yields_unknown_not_zero():
    snap = _snap(volume_5m_cumulative=None)
    assert ms._volume_delta(snap, 1000.0, datetime.now(UTC)) is None


def test_delta_is_difference_between_readings():
    now = datetime.now(UTC)
    prev = _snap(volume_5m_cumulative=1000.0, observed_at=now - timedelta(seconds=60))
    assert ms._volume_delta(prev, 1500.0, now) == pytest.approx(500.0)


def test_missing_current_volume_is_unknown():
    now = datetime.now(UTC)
    prev = _snap(volume_5m_cumulative=1000.0, observed_at=now - timedelta(seconds=60))
    assert ms._volume_delta(prev, None, now) is None


def test_sliding_window_decrease_clamps_to_zero():
    now = datetime.now(UTC)
    prev = _snap(volume_5m_cumulative=5000.0, observed_at=now - timedelta(seconds=60))
    assert ms._volume_delta(prev, 1000.0, now) == 0.0


def test_out_of_order_reading_is_unknown():
    now = datetime.now(UTC)
    prev = _snap(volume_5m_cumulative=1000.0, observed_at=now + timedelta(seconds=60))
    assert ms._volume_delta(prev, 2000.0, now) is None


def test_stale_reading_is_unknown():
    now = datetime.now(UTC)
    prev = _snap(volume_5m_cumulative=1000.0, observed_at=now - timedelta(hours=5))
    assert ms._volume_delta(prev, 2000.0, now) is None


def _snap(volume_5m_cumulative=None, observed_at=None):
    from app.models.market import MarketSnapshot

    return MarketSnapshot(
        pair_id="p",
        price_usd=1.0,
        liquidity_usd=1.0,
        volume_5m_cumulative=volume_5m_cumulative,
        observed_at=observed_at or datetime.now(UTC),
        source="dexscreener",
    )


# ----------------------------- Completeness & filters -----------------------------


def test_missing_fields_detected():
    p = _pair(dex_id=None)
    assert "dex_id" in ms.missing_fields(p)


def test_complete_pair_has_no_missing_fields():
    assert ms.missing_fields(_pair()) == []


def test_incomplete_pair_is_dropped_by_default():
    pairs = [_pair(), _pair(pair_address="p2", dex_id=None)]
    kept = ms.apply_discovery_filters(pairs, ms.default_filters())
    assert [x.pair_address for x in kept] == ["pair-1"]


def test_incomplete_pair_allowed_when_opted_in():
    rules = {**ms.default_filters(), "allow_incomplete": True}
    pairs = [_pair(), _pair(pair_address="p2", dex_id=None)]
    kept = ms.apply_discovery_filters(pairs, rules)
    assert len(kept) == 2


def test_low_liquidity_is_filtered():
    kept = ms.apply_discovery_filters([_pair(liquidity_usd=1.0)], ms.default_filters())
    assert kept == []


def test_filters_never_turn_unknown_into_a_pass():
    """A None threshold input must not be treated as zero volume."""
    rules = {**ms.default_filters(), "min_volume_24h_usd": 100.0}
    kept = ms.apply_discovery_filters([_pair(volume_24h=None)], rules)
    assert kept == []


def test_ingest_reports_filtered_counts(db):
    result = ms.ingest_pairs(
        db, [_pair(), _pair(pair_address="p2", dex_id=None)], filters=ms.default_filters()
    )
    assert result["received"] == 2
    assert result["ingested"] == 1
    assert result["filtered_out"] == 1