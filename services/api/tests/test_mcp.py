import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.mcp_server import mcp


@pytest.fixture
def client():
    return TestClient(app)


def test_mcp_info_endpoint(client):
    res = client.get("/api/v1/mcp/info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["name"] == "sofia-intelligence"
    assert data["counts"]["tools"] >= 10
    assert data["counts"]["resources"] >= 3
    assert data["counts"]["prompts"] >= 3


def test_mcp_tools_catalog(client):
    res = client.get("/api/v1/mcp/tools")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 10
    tool_names = [t["name"] for t in data["tools"]]
    assert "analyze_stock" in tool_names
    assert "analyze_crypto" in tool_names
    assert "get_gold_market" in tool_names
    assert "calculate_deposito_vs_bonds" in tool_names
    assert "analyze_memecoin_rugcheck" in tool_names


def test_mcp_call_tool_deposito_calculator(client):
    payload = {
        "tool": "calculate_deposito_vs_bonds",
        "arguments": {
            "nominal_idr": 20000000,
            "tenor_days": 30,
            "deposito_rate_pct": 5.0,
            "bond_rate_pct": 6.5,
            "is_syariah": True,
        },
    }
    res = client.post("/api/v1/mcp/call", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    result = data["result"]
    assert result["nominal_idr"] == 20000000
    assert "Deposito Syariah" in result["deposito"]["label"]
    assert result["deposito"]["tax_pph_20_idr"] > 0
    assert result["obligasi_sbn"]["tax_pph_10_idr"] > 0


def test_mcp_call_tool_encyclopedia(client):
    payload = {
        "tool": "lookup_market_encyclopedia",
        "arguments": {"keyword": "mudharabah"},
    }
    res = client.post("/api/v1/mcp/call", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "syariah" in data["result"]["explanation"].lower()


def test_mcp_resources_and_prompts(client):
    res_r = client.get("/api/v1/mcp/resources")
    assert res_r.status_code == 200
    assert res_r.json()["total"] >= 6

    res_p = client.get("/api/v1/mcp/prompts")
    assert res_p.status_code == 200
    assert res_p.json()["total"] >= 3


def test_mcp_proxmox_jsonrpc_and_data_snapshot(client):
    # 1. Test JSON-RPC initialize & tools/list
    r_init = client.post(
        "/api/v1/mcp/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r_init.status_code == 200
    assert r_init.json()["result"]["serverInfo"]["name"] == "sofia-intelligence"

    r_list = client.post(
        "/api/v1/mcp/jsonrpc",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert r_list.status_code == 200
    names = [t["name"] for t in r_list.json()["result"]["tools"]]
    assert "get_bot_status_and_logs" in names
    assert "get_trading_journal" in names
    assert "get_wallets_and_treasury" in names
    assert "get_portfolio_status" in names

    # 2. Test JSON-RPC tools/call for get_bot_status_and_logs & get_portfolio_status
    r_call = client.post(
        "/api/v1/mcp/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_bot_status_and_logs", "arguments": {"limit": 5}},
        },
    )
    assert r_call.status_code == 200
    assert r_call.json()["result"]["isError"] is False
    assert r_call.json()["result"]["data"]["status"] == "success"

    # 3. Test Proxmox guide & data-snapshot endpoints
    r_guide = client.get("/api/v1/mcp/proxmox-guide")
    assert r_guide.status_code == 200
    assert "jsonrpc_2_0" in r_guide.json()["endpoints"]

    r_snap = client.get("/api/v1/mcp/data-snapshot?mode=PAPER")
    assert r_snap.status_code == 200
    snap = r_snap.json()
    assert snap["status"] == "online"
    assert snap["portfolio"]["status"] == "success"
    assert snap["bot"]["status"] == "success"
