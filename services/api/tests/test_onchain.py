"""On-chain intelligence tests (FR-AE-004).

The contract under test: safety-critical facts come from Solana RPC, never from
an LLM, and an unverifiable check stays UNKNOWN instead of becoming a PASS.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from app.core.errors import ProviderError
from app.providers.onchain.solana_rpc import SolanaRPCProvider, _concentration
from app.services import onchain_service
from app.services.onchain_service import TokenFacts


class FakeRPC:
    """Stands in for SolanaRPCProvider; returns canned RPC payloads."""

    name = "solana_rpc"

    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    async def collect_token_facts(self, mint, holder_limit=20):
        if self.error:
            raise self.error
        return dict(self.payload)


def _payload(**over):
    base = {
        "status": "OK",
        "error": None,
        "mint_authority_revoked": True,
        "freeze_authority_revoked": True,
        "supply_raw": "1000000000",
        "decimals": 9,
        "top10_holder_pct": 0.30,
        "top20_holder_pct": 0.45,
        "holder_accounts_scanned": 20,
        "is_frozen": False,
        "provider": "solana_rpc",
    }
    base.update(over)
    return base


def _token(db, mint="So11111111111111111111111111111111111111112"):
    from app.models.market import Token

    t = Token(chain="solana", mint_address=mint, symbol="T")
    db.add(t)
    db.commit()
    return t


# ----------------------------- Concentration math -----------------------------


def test_concentration_computes_top10_and_top20():
    supply = 1000
    balances = list(range(1, 21))  # 1..20
    top10, top20, scanned = _concentration(str(supply), len(balances), balances)
    assert scanned == 20
    assert top20 == pytest.approx(sum(balances) / supply)
    assert top10 == pytest.approx(sum(balances[-10:]) / supply)
    assert 0 < top10 < top20 <= 1.0


def test_concentration_unknown_when_supply_missing():
    assert _concentration(None, 5, [1, 2, 3]) == (None, None, 0)


def test_concentration_unknown_when_balances_missing():
    assert _concentration("1000", 0, []) == (None, None, 0)
    assert _concentration("1000", 0, None) == (None, None, 0)


def test_concentration_never_exceeds_one():
    # Double counting a balance would push the ratio above 1.
    balances = [1000] * 20
    top10, top20, _ = _concentration("1000", 20, balances)
    assert top10 == 1.0
    assert top20 == 1.0


def test_concentration_handles_zero_supply():
    assert _concentration("0", 3, [1, 2, 3]) == (None, None, 0)


# ----------------------------- Provider behaviour -----------------------------


def test_collect_facts_marks_revoked_authorities():
    rpc = SolanaRPCProvider(url="http://test.invalid")

    async def fake_call(method, params, max_retries=2):
        if method == "getAccountInfo":
            return {
                "value": {
                    "data": {
                        "parsed": {
                            "info": {
                                "mintAuthority": "",
                                "freezeAuthority": "",
                                "supply": "1000",
                                "decimals": "6",
                                "isFrozen": False,
                            }
                        }
                    }
                }
            }
        if method == "getTokenLargestAccounts":
            return {"value": [{"address": "a"}, {"address": "b"}]}
        if method == "getMultipleAccounts":
            return {
                "value": [
                    {"data": {"parsed": {"info": {"tokenAmount": {"amount": "600"}}}}},
                    {"data": {"parsed": {"info": {"tokenAmount": {"amount": "100"}}}}},
                ]
            }
        raise AssertionError("unexpected method " + method)

    rpc._call = fake_call
    facts = asyncio.run(rpc.collect_token_facts("MintAddress"))
    assert facts["status"] == "OK"
    assert facts["mint_authority_revoked"] is True
    assert facts["freeze_authority_revoked"] is True
    assert facts["top20_holder_pct"] == pytest.approx(0.70)


def test_collect_facts_detects_live_authorities():
    rpc = SolanaRPCProvider(url="http://test.invalid")

    async def fake_call(method, params, max_retries=2):
        if method == "getAccountInfo":
            return {
                "value": {
                    "data": {
                        "parsed": {
                            "info": {
                                "mintAuthority": "SomeAuthority111111111111111111111111",
                                "freezeAuthority": "FreezerAuthority11111111111111111111",
                                "supply": "1000",
                                "decimals": "6",
                            }
                        }
                    }
                }
            }
        return {"value": []}

    rpc._call = fake_call
    facts = asyncio.run(rpc.collect_token_facts("MintAddress"))
    assert facts["mint_authority_revoked"] is False
    assert facts["freeze_authority_revoked"] is False


def test_collect_facts_on_missing_account_is_not_a_pass():
    rpc = SolanaRPCProvider(url="http://test.invalid")

    async def fake_call(method, params, max_retries=2):
        return {"value": None}

    rpc._call = fake_call
    facts = asyncio.run(rpc.collect_token_facts("MintAddress"))
    assert facts["status"] == "NOT_FOUND"
    # Crucially NOT False: an absent account is not a revoked authority.
    assert facts["mint_authority_revoked"] is None
    assert facts["freeze_authority_revoked"] is None


def test_collect_facts_on_rpc_error_is_not_a_pass():
    rpc = SolanaRPCProvider(url="http://test.invalid")

    async def fake_call(method, params, max_retries=2):
        raise ProviderError("solana_rpc", "HTTP 503")

    rpc._call = fake_call
    facts = asyncio.run(rpc.collect_token_facts("MintAddress"))
    assert facts["status"] == "ERROR"
    assert facts["mint_authority_revoked"] is None
    assert facts["freeze_authority_revoked"] is None


# ----------------------------- Persistence -----------------------------


def test_refresh_persists_and_caches(db):
    token = _token(db)
    facts = onchain_service.refresh_facts(db, token, provider=FakeRPC(_payload()))
    assert facts.verified
    assert facts.mint_authority_revoked is True
    cached = onchain_service.get_cached_facts(db, token)
    assert cached is not None
    assert cached.top10_holder_pct == 0.30


def test_refresh_updates_decimals_on_token(db):
    token = _token(db)
    assert token.decimals is None
    onchain_service.refresh_facts(db, token, provider=FakeRPC(_payload(decimals=6)))
    db.refresh(token)
    assert token.decimals == 6


def test_error_is_persisted_as_unknown_not_revoked(db):
    token = _token(db)
    facts = onchain_service.refresh_facts(
        db, token, provider=FakeRPC(error=ProviderError("solana_rpc", "timeout"))
    )
    assert facts.status == "ERROR"
    assert facts.mint_authority_revoked is None
    assert facts.freeze_authority_revoked is None
    assert facts.top10_holder_pct is None


def test_stale_facts_are_not_fresh(db):
    token = _token(db)
    onchain_service.refresh_facts(db, token, provider=FakeRPC(_payload()))
    assert onchain_service.is_fresh(onchain_service.get_cached_facts(db, token))

    from app.models.market import OnchainTokenFacts

    row = db.query(OnchainTokenFacts).filter(OnchainTokenFacts.token_id == token.id).first()
    row.observed_at = datetime.now(UTC) - timedelta(days=2)
    db.commit()
    assert not onchain_service.is_fresh(onchain_service.get_cached_facts(db, token))


def test_fresh_cached_facts_avoid_a_second_rpc_call(db):
    token = _token(db)
    calls = []

    class Counting(FakeRPC):
        async def collect_token_facts(self, mint, holder_limit=20):
            calls.append(mint)
            return _payload()

    onchain_service.refresh_facts(db, token, provider=Counting())
    onchain_service.get_or_fetch(db, token, provider=Counting())
    assert len(calls) == 1, "fresh facts must not trigger another RPC round trip"


def test_get_or_fetch_without_network_returns_unavailable(db):
    token = _token(db)
    facts = onchain_service.get_or_fetch(db, token, provider=FakeRPC(_payload()), allow_network=False)
    assert facts.status == "UNAVAILABLE"
    assert facts.mint_authority_revoked is None


# ----------------------------- The AI boundary -----------------------------


def test_ai_context_cannot_override_onchain_facts(db):
    """A hallucinated PASS from the model must not reach the risk gate."""
    from datetime import UTC as _UTC

    from app.models.market import Candle, MarketSnapshot, TokenPair
    from app.services.analysis_service import run_analysis

    token = _token(db)
    pair = TokenPair(token_id=token.id, pair_address="p1", dex_id="raydium", source="dexscreener")
    db.add(pair)
    db.flush()
    now = datetime.now(_UTC)
    db.add(
        MarketSnapshot(
            pair_id=pair.id,
            price_usd=1.0,
            liquidity_usd=100_000.0,
            volume_1h=50_000.0,
            buys_1h=500,
            observed_at=now,
            source="dexscreener",
        )
    )
    base = now - timedelta(minutes=200)
    for i in range(60):
        price = 1.0 + i * 0.001
        db.add(
            Candle(
                pair_id=pair.id,
                timeframe="M1",
                open_time=base + timedelta(minutes=i),
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price * 1.002,
                volume=1000.0,
                is_final=1,
            )
        )
    db.commit()

    # RPC knows nothing: the authority checks are unverifiable.
    unknown = TokenFacts(mint_address=token.mint_address, status="ERROR")
    # The model confidently claims everything is fine.
    optimistic = {
        "mint_authority_revoked": True,
        "freeze_authority_revoked": True,
        "top10_holder_pct": 0.05,
    }

    run = run_analysis(db, token, pair, ai_context=optimistic, onchain_facts=unknown)
    assert run.decision == "REJECT", "unknown authority must reject regardless of model output"
    assert run.risk_assessment_id is not None


def test_evidence_for_risk_preserves_unknown():
    assert onchain_service.evidence_for_risk(None) == {
        "mint_authority_revoked": None,
        "freeze_authority_revoked": None,
        "top10_holder_pct": None,
    }
    facts = TokenFacts(mint_address="x", mint_authority_revoked=False, status="OK")
    ev = onchain_service.evidence_for_risk(facts)
    assert ev["mint_authority_revoked"] is False


def test_facts_to_json_is_serialisable(db):
    token = _token(db)
    facts = onchain_service.refresh_facts(db, token, provider=FakeRPC(_payload()))
    import json

    payload = json.dumps(facts.to_json())
    assert "mint_authority_revoked" in payload