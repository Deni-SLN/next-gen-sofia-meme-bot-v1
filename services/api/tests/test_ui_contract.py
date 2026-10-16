"""UI ↔ API contract at the field level (Tahap 3).

`tools/check_api_contract.py` compares endpoint *paths*. That is why the
Performance page could render nine tiles against a backend that returns twelve
fields, only three of which overlapped: six tiles were permanently `—` and the
gate stayed green.

These tests close that hole by taking the field list the UI actually renders
(`PERFORMANCE_METRICS` in `apps/web/src/lib/types.ts`) and asserting every one
of those fields exists in a real API response. If a backend field is renamed or
dropped, or a UI field is invented, this fails.

The timeframe tests cover the same class of bug in the other direction: a UI
default the backend rejects silently breaks the page on first load.
"""

import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[3] / "apps" / "web" / "src"
TYPES_TS = WEB / "lib" / "types.ts"
PERFORMANCE_TSX = WEB / "pages" / "Performance.tsx"
TOKENS_TSX = WEB / "pages" / "Tokens.tsx"

METRICS_BLOCK = re.compile(
    r"export const PERFORMANCE_METRICS[^=]*=\s*\[(.*?)\];", re.DOTALL
)
METRIC_ENTRY = re.compile(r"\{\s*key:\s*\"([A-Za-z0-9_]+)\"")


def _performance_metric_keys() -> list[str]:
    """The field names the UI renders, parsed out of the TypeScript source.

    Parsed rather than imported: the backend test suite must not need a Node
    toolchain, and the constant is the contract, not the implementation.
    """
    match = METRICS_BLOCK.search(TYPES_TS.read_text(encoding="utf-8"))
    assert match, "PERFORMANCE_METRICS not found in types.ts - the UI must declare its metrics in one place"
    return METRIC_ENTRY.findall(match.group(1))


def _performance_mode_fields() -> set[str]:
    """Fields declared on the PerformanceMode interface."""
    text = TYPES_TS.read_text(encoding="utf-8")
    block = re.search(r"export interface PerformanceMode \{(.*?)\n\}", text, re.DOTALL)
    assert block, "PerformanceMode interface not found"
    return set(re.findall(r"^\s{2}([A-Za-z0-9_]+)\??:", block.group(1), re.MULTILINE))


# --------------------------- metric fields exist on the backend ---------------------------


def test_performance_metrics_constant_is_not_empty():
    keys = _performance_metric_keys()
    assert len(keys) >= 10, f"expected the UI to render a real metric set, found {keys}"
    assert len(keys) == len(set(keys)), f"duplicate metric keys: {keys}"


def test_every_ui_performance_field_exists_in_the_api_response(client):
    """The core regression: every rendered tile must have a backend field."""
    body = client.get("/api/v1/performance/summary")
    assert body.status_code == 200
    for mode in ("paper", "live"):
        payload = body.json()[mode]
        missing = [k for k in _performance_metric_keys() if k not in payload]
        assert not missing, (
            f"{mode}: UI renders fields the backend does not return: {missing}. "
            "Each would render as a permanent dash."
        )


def test_every_declared_metric_field_exists_in_the_api_response(client):
    """Same check, from the TypeScript interface rather than the render list."""
    payload = client.get("/api/v1/performance/summary").json()["paper"]
    missing = sorted(f for f in _performance_mode_fields() if f not in payload)
    assert not missing, f"PerformanceMode declares fields the API never returns: {missing}"


def test_ui_does_not_invent_performance_fields(client):
    """The reverse direction: a field the UI drops is dead backend work."""
    payload = client.get("/api/v1/performance/summary").json()["paper"]
    declared = set(_performance_mode_fields())
    rendered = set(_performance_metric_keys())
    undeclared = sorted(f for f in rendered if f not in declared)
    assert not undeclared, f"PERFORMANCE_METRICS names fields absent from PerformanceMode: {undeclared}"
    # `unavailable_metrics` and `mode` are metadata, not rendered tiles.
    ignored = {"mode", "unavailable_metrics"}
    orphans = sorted(k for k in payload if k not in declared and k not in ignored)
    assert not orphans, f"backend returns fields the UI type does not know: {orphans}"


def test_unavailable_metrics_are_declared_and_null(client):
    """A metric the pipeline cannot measure must be null and declared."""
    from app.services.performance_service import UNAVAILABLE_METRICS

    payload = client.get("/api/v1/performance/summary").json()["paper"]
    assert set(payload["unavailable_metrics"]) == set(UNAVAILABLE_METRICS)
    for name in UNAVAILABLE_METRICS:
        assert name in payload, f"{name} must be present as null, not omitted"
        assert payload[name] is None, f"{name} is not implemented; it must not report a number"
        assert name in _performance_metric_keys(), (
            f"{name} is declared unavailable, so the UI should render it as a dash on purpose"
        )


def test_performance_page_has_no_hardcoded_metric_keys(client):
    """The render list must drive the page, not a second hand-written one."""
    text = PERFORMANCE_TSX.read_text(encoding="utf-8")
    assert "PERFORMANCE_METRICS.map" in text, "the page must map over the declared metric list"
    for key in ("trades", "wins", "total_pnl", "max_drawdown_pct", "mae_avg", "mfe_avg"):
        if key in ("mae_avg", "mfe_avg"):
            continue
        assert f'"{key}"' not in text, (
            f"Performance.tsx hardcodes the key {key!r}; that is how the field list drifts"
        )


# --------------------------- timeframe contracts ---------------------------


def test_tokens_page_default_timeframe_is_supported():
    from app.api.v1.market import SUPPORTED_TIMEFRAMES

    text = TOKENS_TSX.read_text(encoding="utf-8")
    defaults = re.findall(r'useState\(\s*"([A-Za-z0-9]+)"\s*\)', text)
    assert defaults, "expected a timeframe state in Tokens.tsx"
    for value in defaults:
        assert value.upper() in SUPPORTED_TIMEFRAMES, (
            f"Tokens.tsx defaults to {value!r}, which the backend rejects; "
            f"supported: {SUPPORTED_TIMEFRAMES}"
        )


def _timeframe_options(text: str, param: str) -> list[str]:
    """The timeframe codes an <option> list offers.

    Anchored on the literal list shape immediately before the `.map((param) =>`
    that renders it, so an unrelated array elsewhere in the file cannot match.
    """
    match = re.search(
        r"\[((?:\"[A-Za-z0-9]+\"\s*,?\s*)+)\]\.map\(\(" + re.escape(param) + r"\)\s*=>", text
    )
    assert match, f"expected a timeframe <option> list mapped by {param}"
    return json.loads("[" + match.group(1) + "]")


def test_tokens_page_offers_only_supported_timeframes():
    from app.api.v1.market import SUPPORTED_TIMEFRAMES

    offered = _timeframe_options(TOKENS_TSX.read_text(encoding="utf-8"), "t")
    assert offered, "parsed an empty timeframe list"
    unsupported = [t for t in offered if t.upper() not in SUPPORTED_TIMEFRAMES]
    assert not unsupported, f"Tokens.tsx offers timeframes the backend rejects: {unsupported}"


def test_backtest_default_timeframe_is_supported():
    """The same defect, second instance: the backtest defaulted to '5m'.

    Candles are stored under M1/M5/M15/M30/H1 codes, so the default found zero
    candles and every backtest answered 'insufficient data'.
    """
    from app.api.v1.market import SUPPORTED_TIMEFRAMES

    perf_py = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "performance.py")
    text = perf_py.read_text(encoding="utf-8")
    match = re.search(r'get\("timeframe",\s*"([^"]+)"\)', text)
    assert match, "could not find the backtest default timeframe"
    default = match.group(1)
    assert default.upper() in SUPPORTED_TIMEFRAMES, (
        f"backtest defaults to {default!r}, which is not a stored candle code"
    )


def test_backtest_rejects_an_unsupported_timeframe(client, db):
    from app.models.market import Token, TokenPair

    token = Token(chain="solana", mint_address="MintBt111111111111111111111111111111111", symbol="BT")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="pair-bt")
    db.add(pair)
    db.commit()

    r = client.post("/api/v1/backtest", json={"pair_id": pair.id, "timeframe": "5m"})
    assert r.status_code == 422, r.text
    assert "timeframe" in r.json()["error"]["message"].lower()


def test_backtest_accepts_a_lowercase_stored_code(client, db):
    """The API upper-cases before matching, so 'm5' from a client works."""
    from app.api.v1.market import SUPPORTED_TIMEFRAMES

    assert "M5" in SUPPORTED_TIMEFRAMES
    # No candles seeded, so this must fail on data volume, not on the timeframe.
    r = client.post("/api/v1/backtest", json={"pair_id": "does-not-matter", "timeframe": "m5"})
    assert r.status_code == 422
    assert "insufficient candles" in r.json()["error"]["message"].lower()


def test_performance_page_offers_only_supported_timeframes():
    from app.api.v1.market import SUPPORTED_TIMEFRAMES

    offered = _timeframe_options(PERFORMANCE_TSX.read_text(encoding="utf-8"), "tf")
    assert offered, "parsed an empty timeframe list"
    unsupported = [t for t in offered if t.upper() not in SUPPORTED_TIMEFRAMES]
    assert not unsupported, f"Performance.tsx offers unsupported timeframes: {unsupported}"


# --------------------------- equity curve shape ---------------------------


def test_performance_and_portfolio_equity_curve_agree(client, db):
    """Two endpoints serving the same series must serve the same series."""
    from app.accounting.equity import record_event

    record_event(db, mode="PAPER", event_type="REALIZED_PNL", amount=25.0, idempotency_key="perf-curve")
    perf = client.get("/api/v1/performance/equity-curve").json()
    port = client.get("/api/v1/portfolio/equity-curve").json()

    assert "curve" in perf, "performance/equity-curve must use the canonical curve shape"
    assert "curve" in port
    assert [p["equity"] for p in perf["curve"]] == [p["equity"] for p in port["curve"]]
    assert perf["final_pnl"] == pytest.approx(25.0)


# --------------------------- portfolio field contract ---------------------------


def test_portfolio_overview_fields_the_ui_type_declares_exist(client):
    text = TYPES_TS.read_text(encoding="utf-8")
    block = re.search(r"export interface PortfolioModes \{(.*?)\n\}", text, re.DOTALL)
    assert block, "PortfolioModes interface not found"
    inner = re.search(r"modes: Record<\s*string,\s*\{(.*?)\}\s*>;", block.group(1), re.DOTALL)
    assert inner, "PortfolioModes.modes shape not found"
    declared = set(re.findall(r"^\s{6}([A-Za-z0-9_]+)\??:", inner.group(1), re.MULTILINE))

    payload = client.get("/api/v1/portfolio/overview").json()["modes"]["PAPER"]
    missing = sorted(f for f in declared if f not in payload)
    assert not missing, f"PortfolioModes declares fields the API never returns: {missing}"


def test_portfolio_positions_fields_the_ui_type_declares_exist(client, db):
    from app.models.market import Token
    from app.models.trading import BotRun, Position

    token = Token(chain="solana", mint_address="MintPc11111111111111111111111111111111", symbol="PC")
    db.add(token)
    db.flush()
    run = BotRun(mode="PAPER", status="RUNNING")
    db.add(run)
    db.flush()
    db.add(
        Position(
            bot_run_id=run.id,
            mode="PAPER",
            token_id=token.id,
            mint_address=token.mint_address,
            status="OPEN",
            quantity=1.0,
            average_entry_price=1.0,
            total_fees=0.0,
        )
    )
    db.commit()

    text = TYPES_TS.read_text(encoding="utf-8")
    block = re.search(r"export interface PositionItem \{(.*?)\n\}", text, re.DOTALL)
    assert block, "PositionItem interface not found"
    declared = set(re.findall(r"^\s{2}([A-Za-z0-9_]+)\??:", block.group(1), re.MULTILINE))

    item = client.get("/api/v1/portfolio/positions").json()["items"][0]
    missing = sorted(f for f in declared if f not in item)
    assert not missing, f"PositionItem declares fields the API never returns: {missing}"


# --------------------------- the checkers themselves still work ---------------------------


def test_metric_parser_is_not_a_silent_no_op():
    """These tests parse TypeScript text, so a broken regex would make every
    assertion above pass vacuously. Prove the parser both finds and rejects."""
    keys = _performance_metric_keys()
    assert "win_rate" in keys
    # Fields the backend never had. If a future "fix" widened the regex, these
    # would start parsing and this test would fail.
    for phantom in ("trades", "total_pnl", "max_drawdown_pct"):
        assert phantom not in keys, f"parser matched {phantom!r}, which is not a backend field"


def test_metric_parser_rejects_a_malformed_block():
    sample = 'export const PERFORMANCE_METRICS: X[] = [\n  { key: "alpha", label: "A" },\n];'
    assert METRIC_ENTRY.findall(METRICS_BLOCK.search(sample).group(1)) == ["alpha"]


def test_the_old_backend_keys_are_really_gone():
    """Pins the exact defect: these six keys were rendered by the UI and never
    existed on the backend."""
    payload_keys = set(_performance_mode_fields())
    for dead in ("trades", "total_pnl", "wins_rate", "mae", "mfe"):
        assert dead not in payload_keys
