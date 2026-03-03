"""API key authentication middleware for the MCP endpoint."""

import logging

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class MCPAuthMiddleware:
    """ASGI middleware that validates x-api-key header before passing to MCP server.

    Wraps the MCP Starlette app. Requests without a valid API key get 401.
    If no API key is configured, returns 503.
    """

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if not self.api_key:
                response = JSONResponse(
                    status_code=503,
                    content={"error": "MCP endpoint not configured (API key missing)"},
                )
                await response(scope, receive, send)
                return

            headers = dict(scope.get("headers", []))
            provided_key = headers.get(b"x-api-key", b"").decode()

            if provided_key != self.api_key:
                response = JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or missing API key"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
