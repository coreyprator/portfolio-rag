"""MCP Streamable HTTP endpoint - JSON-RPC handler with API key + Bearer auth."""

import logging

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.mcp_server import query_portfolio, rag_query, rag_get_document
from app.api.oauth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MCP"])

VALID_COLLECTIONS = ["portfolio", "etymology", "code", "jazz_theory", "dcc", "metapm"]

# Tool schemas
TOOL_SCHEMAS = [
    {
        "name": "query_portfolio",
        "description": (
            "Search the portfolio knowledge base. "
            "Returns ranked chunks with source attribution from "
            "PROJECT_KNOWLEDGE.md files, Bootstrap standards, methodology docs, "
            "and etymology references across all portfolio projects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to search: 'portfolio', 'etymology', or omit for all",
                    "enum": ["portfolio", "etymology"],
                },
                "max_results": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum chunks to return (default 5, max 20)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag_query",
        "description": (
            "Semantic search across Portfolio RAG vector database. "
            "Use to retrieve canonical standards documents, Bootstrap sections, "
            "PROJECT_KNOWLEDGE.md content, CAI standards, and methodology docs. "
            "Always use this before writing CC prompts to verify current standards. "
            "Collections: portfolio (methodology/standards), metapm (requirements), "
            "etymology (Beekes dictionary), dcc (Greek core vocab), "
            "code (source code), jazz_theory (jazz harmony)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to search",
                    "enum": VALID_COLLECTIONS,
                    "default": "portfolio",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag_get_document",
        "description": (
            "Retrieve all chunks from a specific document in Portfolio RAG. "
            "Use when rag_query returns a snippet and you need the full document. "
            "Source paths follow the pattern: project/filename.md "
            "Examples: project-methodology/docs/CAI_Outbound_CC_Prompt_Standard.md, "
            "harmonylab/PROJECT_KNOWLEDGE.md, metapm/PROJECT_KNOWLEDGE.md"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Document source path as returned by rag_query",
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to search (default: portfolio)",
                    "default": "portfolio",
                },
            },
            "required": ["source"],
        },
    },
]

TOOL_HANDLERS = {
    "query_portfolio": query_portfolio,
    "rag_query": rag_query,
    "rag_get_document": rag_get_document,
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
    # Path 2: Authorization: Bearer <key-or-token>
    if authorization and authorization.startswith("Bearer "):
        bearer_value = authorization[7:]
        # Accept raw API key or signed OAuth token
        if bearer_value == settings.RAG_API_KEY or verify_token(bearer_value) is not None:
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
            "result": {"tools": TOOL_SCHEMAS},
        }

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return _jsonrpc_error(request_id, -32601, f"Unknown tool: {tool_name}")

        try:
            result_text = await handler(**args)
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
