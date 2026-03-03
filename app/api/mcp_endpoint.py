"""MCP Streamable HTTP endpoint - JSON-RPC handler with API key + Bearer auth."""

import logging

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.mcp_server import query_portfolio
from app.api.oauth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MCP"])

# Tool schema derived from query_portfolio function signature
TOOL_SCHEMA = {
    "name": "query_portfolio",
    "description": (
        "Query the portfolio knowledge base. "
        "Returns relevant context from PROJECT_KNOWLEDGE.md files, "
        "Bootstrap standards, session closeouts, and methodology docs "
        "across all portfolio projects."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language question or keyword search",
            },
            "n_results": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return (default 5, max 20)",
            },
        },
        "required": ["query"],
    },
}


def _check_auth(x_api_key: str | None, authorization: str | None) -> JSONResponse | None:
    """Validate API key or Bearer token. Returns error response if invalid, None if OK."""
    if not settings.RAG_API_KEY:
        return JSONResponse(
            status_code=503,
            content={"error": "MCP endpoint not configured (API key missing)"},
        )
    # Path 1: x-api-key header (original)
    if x_api_key and x_api_key == settings.RAG_API_KEY:
        return None
    # Path 2: Authorization: Bearer <token>
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if verify_token(token) is not None:
            return None
    # Neither path succeeded
    return JSONResponse(
        status_code=401,
        content={"error": "Invalid or missing API key"},
    )


def _jsonrpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


@router.post("/mcp")
async def mcp_handler(
    request: Request,
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """MCP Streamable HTTP endpoint. Handles JSON-RPC 2.0 requests."""
    auth_error = _check_auth(x_api_key, authorization)
    if auth_error:
        return auth_error

    body = await request.json()
    method = body.get("method")
    request_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "Portfolio RAG",
                    "version": settings.VERSION,
                },
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [TOOL_SCHEMA]},
        }

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name != "query_portfolio":
            return _jsonrpc_error(request_id, -32601, f"Unknown tool: {tool_name}")

        try:
            result_text = await query_portfolio(**args)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            }
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return _jsonrpc_error(request_id, -32603, str(e))

    if method == "notifications/initialized":
        # Client notification after initialize - no response needed
        return JSONResponse(status_code=204, content=None)

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")
