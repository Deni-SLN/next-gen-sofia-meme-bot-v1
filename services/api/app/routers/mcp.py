"""
Router for Model Context Protocol (MCP) endpoints.
Provides tool introspection, REST-based tool execution, resource listing,
and status metadata for external AI agents such as Hermes Agent and OpenClaw.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.mcp_server import mcp

router = APIRouter()


class ToolCallRequest(BaseModel):
    tool: str = Field(..., description="Nama tool MCP yang ingin dipanggil (misal: 'analyze_stock', 'get_gold_market')")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parameter argumen tool dalam bentuk dictionary JSON")


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
