"""
Router for Model Context Protocol (MCP) endpoints.
Provides tool introspection, REST-based tool execution, resource listing,
and status metadata for external AI agents such as Hermes Agent and OpenClaw.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.mcp_server import (
    mcp,
    get_portfolio_status,
    get_bot_status_and_logs,
    get_market_pulse,
    get_gold_market,
    get_trading_signals,
    search_market_news,
    get_wallets_and_treasury,
)

router = APIRouter()


class ToolCallRequest(BaseModel):
    tool: str = Field(..., description="Nama tool MCP yang ingin dipanggil (misal: 'analyze_stock', 'get_gold_market')")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parameter argumen tool dalam bentuk dictionary JSON")


class JsonRpcRequest(BaseModel):
    jsonrpc: str = Field(default="2.0")
    id: Optional[Any] = Field(default=1)
    method: str = Field(..., description="Metode JSON-RPC MCP: 'initialize', 'tools/list', 'tools/call', 'resources/list', 'resources/read', 'prompts/list', 'ping'")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.get("/info", summary="Informasi Server MCP SOFIA")
async def get_mcp_info():
    """Mengembalikan metadata server MCP, deskripsi kapabilitas, dan jumlah tools/resources/prompts yang aktif."""
    tools = mcp._tool_manager.list_tools()
    resources = mcp._resource_manager.list_resources()
    prompts = mcp._prompt_manager.list_prompts()
    
    return {
        "status": "online",
        "name": mcp.name,
        "instructions": mcp.instructions,
        "protocols": ["mcp-stdio-v1", "mcp-sse-v1", "http-jsonrpc"],
        "counts": {
            "tools": len(tools),
            "resources": len(resources),
            "prompts": len(prompts),
        },
        "sse_endpoint": "/mcp/sse",
    }


@router.get("/tools", summary="Daftar Tool MCP yang Tersedia")
async def list_mcp_tools():
    """
    Mengembalikan katalog lengkap Tool MCP SOFIA dengan format standar JSON Schema.
    Kompatibel langsung dengan Hermes Function Calling, OpenClaw, OpenAI Function Calling, dan Anthropic Tools.
    """
    tools = mcp._tool_manager.list_tools()
    catalog = []
    for t in tools:
        catalog.append({
            "name": t.name,
            "description": (t.description or "").strip(),
            "parameters": t.parameters,
        })
    return {
        "total": len(catalog),
        "tools": catalog,
    }


@router.post("/call", summary="Eksekusi Tool MCP via HTTP")
async def call_mcp_tool(req: ToolCallRequest):
    """
    Menjalankan tool MCP secara langsung melalui HTTP POST request.
    Sangat berguna untuk OpenClaw atau agen berbasis webhook/REST yang ingin mengambil data finansial SOFIA tanpa koneksi stdio.
    """
    tools_dict = {t.name: t for t in mcp._tool_manager.list_tools()}
    if req.tool not in tools_dict:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{req.tool}' tidak ditemukan. Panggil GET /api/v1/mcp/tools untuk melihat daftar tools yang valid.",
        )
    
    try:
        call_res = await mcp.call_tool(req.tool, req.arguments)
        # call_tool returns a tuple: (content_list, extra_dict)
        contents, extra = call_res
        parsed_result = None
        if contents and len(contents) > 0:
            import json
            try:
                parsed_result = json.loads(contents[0].text)
            except Exception:
                parsed_result = contents[0].text
        
        return {
            "status": "success",
            "tool": req.tool,
            "result": parsed_result or extra.get("result"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengeksekusi tool '{req.tool}': {str(e)}")


@router.get("/resources", summary="Daftar Resource MCP")
async def list_mcp_resources():
    """Daftar resource statis/dinamis yang disediakan server MCP (misal: 'sofia://market/pulse', 'sofia://gold/prices')."""
    resources = mcp._resource_manager.list_resources()
    res_list = []
    for r in resources:
        res_list.append({
            "uri": str(r.uri),
            "name": r.name,
            "description": r.description or "",
            "mimeType": r.mime_type or "application/json",
        })
    return {
        "total": len(res_list),
        "resources": res_list,
    }


@router.get("/prompts", summary="Daftar Template Prompt MCP")
async def list_mcp_prompts():
    """Daftar template prompt riset pasar yang siap digunakan oleh agen Hermes / OpenClaw."""
    prompts = mcp._prompt_manager.list_prompts()
    prompt_list = []
    for p in prompts:
        prompt_list.append({
            "name": p.name,
            "description": p.description or "",
            "arguments": [
                {"name": arg.name, "description": arg.description or "", "required": arg.required}
                for arg in (p.arguments or [])
            ],
        })
    return {
        "total": len(prompt_list),
        "prompts": prompt_list,
    }


@router.post("/jsonrpc", summary="Endpoint Standar JSON-RPC 2.0 untuk Aplikasi Proxmox & Agent Eksternal")
async def mcp_jsonrpc_endpoint(req: JsonRpcRequest):
    """
    Endpoint stateless JSON-RPC 2.0 untuk aplikasi lain di jaringan Proxmox (LXC/VM, n8n, Home Assistant, OpenClaw, Claude, dsb).
    Mendukung metode standar MCP: 'initialize', 'ping', 'tools/list', 'tools/call', 'resources/list', 'resources/read', 'prompts/list'.
    """
    import json

    method = (req.method or "").strip()
    params = req.params or {}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req.id, "result": {"status": "pong", "server": mcp.name}}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": mcp.name,
                    "version": "3.9.0",
                },
                "instructions": mcp.instructions,
            },
        }

    if method == "tools/list":
        tools = mcp._tool_manager.list_tools()
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "tools": [
                    {
                        "name": t.name,
                        "description": (t.description or "").strip(),
                        "inputSchema": t.parameters,
                    }
                    for t in tools
                ]
            },
        }

    if method == "tools/call":
        tool_name = params.get("name") or params.get("tool")
        tool_args = params.get("arguments") or {}
        tools_dict = {t.name: t for t in mcp._tool_manager.list_tools()}
        if not tool_name or tool_name not in tools_dict:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' tidak ditemukan."},
            }
        try:
            call_res = await mcp.call_tool(tool_name, tool_args)
            contents, extra = call_res
            text_out = contents[0].text if (contents and len(contents) > 0) else json.dumps(extra.get("result", {}))
            parsed_data = None
            try:
                parsed_data = json.loads(text_out)
            except Exception:
                parsed_data = text_out
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {
                    "content": [{"type": "text", "text": text_out}],
                    "data": parsed_data,
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32000, "message": str(exc)},
            }

    if method == "resources/list":
        resources = mcp._resource_manager.list_resources()
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "resources": [
                    {
                        "uri": str(r.uri),
                        "name": r.name,
                        "description": r.description or "",
                        "mimeType": r.mime_type or "application/json",
                    }
                    for r in resources
                ]
            },
        }

    if method == "resources/read":
        uri = str(params.get("uri") or "")
        try:
            res_content = await mcp.read_resource(uri)
            text_payload = res_content if isinstance(res_content, str) else json.dumps(res_content, default=str)
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": text_payload,
                        }
                    ]
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32602, "message": f"Resource '{uri}' gagal dibaca: {exc}"},
            }

    if method == "prompts/list":
        prompts = mcp._prompt_manager.list_prompts()
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description or "",
                        "arguments": [
                            {"name": arg.name, "description": arg.description or "", "required": arg.required}
                            for arg in (p.arguments or [])
                        ],
                    }
                    for p in prompts
                ]
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": {"code": -32601, "message": f"Metode JSON-RPC '{method}' tidak didukung."},
    }


@router.get("/data-snapshot", summary="Snapshot Data Lengkap SOFIA untuk Aplikasi Lain di Proxmox")
async def get_proxmox_data_snapshot(mode: str = Query(default="PAPER", description="Mode portofolio: PAPER atau LIVE")):
    """
    Endpoint jembatan data terpadu (Single-Call Data Bridge) agar aplikasi/container lain di Proxmox
    (seperti n8n, Home Assistant, Grafana, OpenClaw, atau dashboard internal) dapat membaca seluruh data
    penting SOFIA Market 3.9 dalam satu request cepat.
    """
    return {
        "status": "online",
        "server": mcp.name,
        "portfolio": get_portfolio_status(mode=mode),
        "bot": get_bot_status_and_logs(limit=10),
        "market_pulse": get_market_pulse(),
        "gold_market": get_gold_market(),
        "signals": get_trading_signals(status="pending", limit=5),
        "news_geopolitik": search_market_news(category="geopolitik", limit=4),
        "news_headline": search_market_news(category="all", limit=4),
        "wallets_treasury": get_wallets_and_treasury(),
    }


@router.get("/proxmox-guide", summary="Panduan Integrasi MCP SOFIA Antar-Container/VM di Proxmox")
async def get_proxmox_integration_guide(request: Request):
    """
    Mengembalikan konfigurasi siap-pakai (URL SSE, JSON-RPC 2.0, REST Call, dan Data Snapshot)
    untuk menghubungkan aplikasi lain di jaringan Proxmox ke SOFIA Market 3.9.
    """
    host = request.headers.get("host") or "127.0.0.1:8000"
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    base_url = f"{scheme}://{host}"
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    resources = [str(r.uri) for r in mcp._resource_manager.list_resources()]

    return {
        "status": "ready",
        "server_name": mcp.name,
        "base_url": base_url,
        "endpoints": {
            "sse_stream": f"{base_url}/mcp/sse",
            "jsonrpc_2_0": f"{base_url}/api/v1/mcp/jsonrpc",
            "rest_tool_call": f"{base_url}/api/v1/mcp/call",
            "rest_tools_catalog": f"{base_url}/api/v1/mcp/tools",
            "proxmox_data_snapshot": f"{base_url}/api/v1/mcp/data-snapshot",
        },
        "available_tools": tools,
        "available_resources": resources,
        "client_configs": {
            "mcp_sse_client": {
                "mcpServers": {
                    "sofia-intelligence": {
                        "url": f"{base_url}/mcp/sse",
                        "transport": "sse",
                    }
                }
            },
            "curl_jsonrpc_example": (
                f"curl -X POST {base_url}/api/v1/mcp/jsonrpc "
                "-H 'Content-Type: application/json' "
                "-d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"get_bot_status_and_logs\",\"arguments\":{\"limit\":5}}}'"
            ),
            "curl_rest_example": (
                f"curl -X POST {base_url}/api/v1/mcp/call "
                "-H 'Content-Type: application/json' "
                "-d '{\"tool\":\"get_portfolio_status\",\"arguments\":{\"mode\":\"PAPER\"}}'"
            ),
        },
    }
