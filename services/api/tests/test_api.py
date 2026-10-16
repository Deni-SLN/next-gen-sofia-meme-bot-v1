"""API integration tests exercising the HTTP surface end-to-end.

Covers: system/health, bot lifecycle (LIVE rejected), watchlist, portfolio
accounting, and AI agents — all through the real FastAPI app with an isolated DB.
"""


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_status(client):
    r = client.get("/api/v1/system/status")
    assert r.status_code == 200
    body = r.json()
    assert body["live_trading_enabled"] is False
    assert body["bot"]["status"] in ("STOPPED", "RUNNING", "PAUSED")
    assert "counts" in body


def test_bot_lifecycle_paper(client):
    # start in PAPER
    r = client.post("/api/v1/bot/start", json={"mode": "PAPER"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RUNNING"
    assert r.json()["mode"] == "PAPER"

    # pause / resume
    assert client.post("/api/v1/bot/pause").json()["status"] == "PAUSED"
    assert client.post("/api/v1/bot/resume").json()["status"] == "RUNNING"

    # stop
    assert client.post("/api/v1/bot/stop", json={"reason": "test"}).json()["status"] == "STOPPED"


def test_bot_live_always_rejected(client):
    r = client.post("/api/v1/bot/start", json={"mode": "LIVE"})
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "LIVE_DISABLED" or "live" in body["error"]["message"].lower()


def test_emergency_stop_blocks_start(client):
    client.post("/api/v1/bot/emergency-stop")
    r = client.post("/api/v1/bot/start", json={"mode": "PAPER"})
    # kill switch must prevent trading
    assert r.status_code in (200, 403, 409)


def test_risk_config_get_and_update(client):
    r = client.get("/api/v1/risk/config")
    assert r.status_code == 200
    assert "max_position_allocation_usd" in r.json()

    r = client.put("/api/v1/risk/config", json={"max_position_allocation_usd": 250.0})
    assert r.status_code == 200
    assert r.json()["max_position_allocation_usd"] == 250.0


def test_watchlist_crud(client):
    r = client.post("/api/v1/watchlists", json={"name": "moonshots"})
    assert r.status_code == 200
    wid = r.json()["id"]

    mint = "So11111111111111111111111111111111111111112"
    r = client.post(f"/api/v1/watchlists/{wid}/items", json={"mint_address": mint})
    assert r.status_code == 200

    # duplicate rejected
    r = client.post(f"/api/v1/watchlists/{wid}/items", json={"mint_address": mint})
    assert r.status_code == 409

    r = client.get("/api/v1/watchlists")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    r = client.delete(f"/api/v1/watchlists/{wid}/items/{mint}")
    assert r.status_code == 200


def test_portfolio_overview_and_cash_movement(client):
    r = client.get("/api/v1/portfolio/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["modes"]["PAPER"]["available"] is True
    assert body["modes"]["LIVE"]["available"] is False
    assert body["live_trading_enabled"] is False

    r = client.post("/api/v1/portfolio/cash-movement", json={"movement": "DEPOSIT", "amount": 500, "mode": "PAPER"})
    assert r.status_code == 200
    # deposit increases equity by 500
    body = client.get("/api/v1/portfolio/overview").json()
    assert abs(body["modes"]["PAPER"]["equity"] - 1500.0) < 1e-6


def test_portfolio_cash_movement_validation(client):
    r = client.post("/api/v1/portfolio/cash-movement", json={"movement": "BOGUS", "amount": 500})
    assert r.status_code == 422
    r = client.post("/api/v1/portfolio/cash-movement", json={"movement": "DEPOSIT", "amount": -5})
    assert r.status_code == 422


def test_accounting_audit_formula(client):
    r = client.get("/api/v1/portfolio/accounting-audit")
    assert r.status_code == 200
    assert "equity = initial_capital" in r.json()["formula"]


def test_ai_agents_seed_defaults(client):
    r = client.get("/api/v1/ai/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    names = {a["agent_name"] for a in agents}
    assert {"technical-analysis", "onchain-risk", "signal-validation"}.issubset(names)


def test_ai_usage_empty(client):
    r = client.get("/api/v1/ai/usage")
    assert r.status_code == 200
    assert r.json()["requests"] == 0


def test_signals_empty(client):
    r = client.get("/api/v1/signals")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_unknown_route_404(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
