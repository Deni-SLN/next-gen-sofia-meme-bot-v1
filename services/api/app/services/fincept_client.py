"""
fincept_client.py — High-Performance Fincept Terminal FastMCP Client.
Connects directly to the self-hosted Fincept Terminal MCP service in Proxmox CT 106
at http://192.168.0.145:18765/mcp to provide:
  1. Macroeconomic indicators (VIX, 10Y Treasury, 2Y Treasury, DXY Dollar Index, WTI Crude Oil)
  2. Multi-asset historical OHLCV market data
  3. Quantitative factor backtesting (IC, Sharpe, Win Rate)
  4. Global ticker symbol search
"""

import json
import logging
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FINCEPT_MCP_URL = "http://192.168.0.145:18765/mcp"

# Module-level session cache
_session_id: Optional[str] = None
_session_timestamp: float = 0
_cache_macro: Optional[Dict[str, Any]] = None
_cache_macro_time: float = 0


def _get_active_session() -> Optional[str]:
    """Initialize or reuse a streamable HTTP MCP session with Fincept Terminal."""
    global _session_id, _session_timestamp
    now = time.time()
    if _session_id and (now - _session_timestamp < 1800):  # 30 min session reuse
        return _session_id

    try:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sofia-market-engine", "version": "4.1.3"}
            }
        }
        req = urllib.request.Request(
            FINCEPT_MCP_URL,
            data=json.dumps(init_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            sid = resp.headers.get("mcp-session-id")
            if sid:
                _session_id = sid
                _session_timestamp = now
                
                # Send initialized notification
                notif_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                notif_req = urllib.request.Request(
                    FINCEPT_MCP_URL,
                    data=json.dumps(notif_payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": sid
                    }
                )
                try:
                    urllib.request.urlopen(notif_req, timeout=3)
                except Exception:
                    pass
                return sid
    except Exception as e:
        logger.warning(f"Failed to connect to Fincept MCP at {FINCEPT_MCP_URL}: {e}")
        return None
    return None


def _call_fincept_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool on the Fincept FastMCP server and return structured data."""
    sid = _get_active_session()
    if not sid:
        return {"error": "Fincept Terminal MCP service unreachable"}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid
    }
    call_payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 100000,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    try:
        req = urllib.request.Request(
            FINCEPT_MCP_URL,
            data=json.dumps(call_payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            for line in body.strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    res = data.get("result", {})
                    # Prefer structuredContent if available
                    if "structuredContent" in res and res["structuredContent"]:
                        return res["structuredContent"]
                    # Otherwise parse text from content array
                    content_list = res.get("content", [])
                    for c in content_list:
                        if c.get("type") == "text" and c.get("text"):
                            try:
                                return json.loads(c["text"])
                            except Exception:
                                return {"raw": c["text"]}
                    return res
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Session expired, clear and retry once
            global _session_id
            _session_id = None
            sid = _get_active_session()
            if sid:
                headers["mcp-session-id"] = sid
                req = urllib.request.Request(
                    FINCEPT_MCP_URL,
                    data=json.dumps(call_payload).encode("utf-8"),
                    headers=headers
                )
                try:
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        body = resp.read().decode("utf-8", errors="replace")
                        for line in body.strip().split("\n"):
                            if line.startswith("data: "):
                                data = json.loads(line[6:])
                                res = data.get("result", {})
                                if "structuredContent" in res and res["structuredContent"]:
                                    return res["structuredContent"]
                                content_list = res.get("content", [])
                                for c in content_list:
                                    if c.get("type") == "text" and c.get("text"):
                                        try:
                                            return json.loads(c["text"])
                                        except Exception:
                                            return {"raw": c["text"]}
                                return res
                except Exception as retry_err:
                    return {"error": str(retry_err)}
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

    return {"error": "Empty response from Fincept MCP"}


def get_macro_indicators(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch comprehensive macroeconomic indicators:
    - US 10-Year Treasury Yield (^TNX)
    - US 2-Year Treasury Yield (^IRX)
    - CBOE Volatility Index VIX (^VIX)
    - US Dollar Index DXY (DX-Y.NYB)
    - WTI Crude Oil
    """
    global _cache_macro, _cache_macro_time
    now = time.time()
    if not force_refresh and _cache_macro and (now - _cache_macro_time < 300):  # 5 min cache
        return _cache_macro

    data = _call_fincept_tool("economics_data", {"indicator": "VIX"})
    if "error" in data or not data.get("indicators"):
        # If cache exists return stale, else return error
        if _cache_macro:
            return _cache_macro
        return data

    raw_ind = data.get("indicators", {})
    vix_val = float((raw_ind.get("vix") or {}).get("value") or 0.0)
    tnx_val = float((raw_ind.get("treasury_10y") or {}).get("value") or 0.0)
    irx_val = float((raw_ind.get("treasury_2y") or {}).get("value") or 0.0)
    dxy_val = float((raw_ind.get("dxy") or {}).get("value") or 0.0)
    oil_val = float((raw_ind.get("oil_wti") or {}).get("value") or 0.0)

    # Market sentiment regime assessment
    if vix_val < 15.0:
        vix_sentiment = "Extremely Complacent (Risk-On)"
    elif vix_val < 20.0:
        vix_sentiment = "Normal Low Volatility (Risk-On)"
    elif vix_val < 25.0:
        vix_sentiment = "Elevated Volatility (Caution)"
    else:
        vix_sentiment = "High Fear / Stress (Risk-Off)"

    # Yield curve 10Y - 2Y spread
    yield_spread = round(tnx_val - irx_val, 3) if tnx_val and irx_val else 0.0
    yield_curve_status = "Inverted (Recession Warning)" if yield_spread < 0 else "Normal (Steepening / Expansion)"

    processed = {
        "source": "Fincept Terminal Quantitative Engine (Proxmox CT 106)",
        "timestamp": data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "online",
        "market_regime": {
            "vix_sentiment": vix_sentiment,
            "yield_curve_status": yield_curve_status,
            "yield_spread_10y_2y": yield_spread,
        },
        "indicators": {
            "vix": {
                "name": "CBOE Volatility Index",
                "ticker": "^VIX",
                "value": vix_val,
                "change_pct": (raw_ind.get("vix") or {}).get("change_pct", 0.0),
                "date": (raw_ind.get("vix") or {}).get("date"),
            },
            "treasury_10y": {
                "name": "US 10-Year Treasury Yield",
                "ticker": "^TNX",
                "value": tnx_val,
                "unit": "%",
                "change_pct": (raw_ind.get("treasury_10y") or {}).get("change_pct", 0.0),
                "date": (raw_ind.get("treasury_10y") or {}).get("date"),
            },
            "treasury_2y": {
                "name": "US 2-Year Treasury Yield",
                "ticker": "^IRX",
                "value": irx_val,
                "unit": "%",
                "change_pct": (raw_ind.get("treasury_2y") or {}).get("change_pct", 0.0),
                "date": (raw_ind.get("treasury_2y") or {}).get("date"),
            },
            "dxy": {
                "name": "US Dollar Index",
                "ticker": "DX-Y.NYB",
                "value": dxy_val,
                "change_pct": (raw_ind.get("dxy") or {}).get("change_pct", 0.0),
                "date": (raw_ind.get("dxy") or {}).get("date"),
            },
            "oil_wti": {
                "name": "WTI Crude Oil",
                "ticker": "CL=F",
                "value": oil_val,
                "unit": "USD/bbl",
                "change_pct": (raw_ind.get("oil_wti") or {}).get("change_pct", 0.0),
                "date": (raw_ind.get("oil_wti") or {}).get("date"),
            },
        }
    }
    _cache_macro = processed
    _cache_macro_time = now
    return processed


def run_factor_backtest(symbol: str, factor_expr: str, period: str = "1y") -> Dict[str, Any]:
    """Run mathematical factor expression backtest over historical price bars."""
    res = _call_fincept_tool("factor_backtest", {
        "symbol": symbol.strip().upper(),
        "factor_expr": factor_expr.strip(),
        "period": period.strip()
    })
    return res


def get_market_data(symbol: str, period: str = "5d", interval: str = "1d") -> Dict[str, Any]:
    """Fetch multi-asset OHLCV bars via Fincept Terminal."""
    return _call_fincept_tool("market_data", {
        "symbol": symbol.strip().upper(),
        "period": period.strip(),
        "interval": interval.strip()
    })


def search_symbols(query: str, limit: int = 10) -> Dict[str, Any]:
    """Universal symbol search across equities and crypto."""
    return _call_fincept_tool("symbol_search", {
        "query": query.strip(),
        "limit": limit
    })
