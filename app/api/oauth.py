"""OAuth 2.0 client_credentials token endpoint for Claude.ai connector."""

import base64
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OAuth"])

TOKEN_EXPIRY_SECONDS = 3600


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(client_id: str) -> str:
    """Create a stateless HMAC-SHA256 signed token."""
    now = int(time.time())
    payload = {"sub": client_id, "iat": now, "exp": now + TOKEN_EXPIRY_SECONDS}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(
        settings.RAG_API_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def verify_token(token: str) -> str | None:
    """Verify an HMAC-SHA256 token. Returns client_id (sub) if valid, None if invalid."""
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    expected_sig = hmac.new(
        settings.RAG_API_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload.get("sub")


@router.post("/oauth/token")
async def token_endpoint(request: Request):
    """OAuth 2.0 client_credentials grant endpoint."""
    if not settings.RAG_API_KEY:
        return JSONResponse(
            status_code=503,
            content={"error": "server_error", "error_description": "Token endpoint not configured"},
        )

    body = await request.body()
    params = dict(
        pair.split("=", 1)
        for pair in body.decode("utf-8").split("&")
        if "=" in pair
    )

    grant_type = params.get("grant_type")
    client_id = params.get("client_id")
    client_secret = params.get("client_secret")

    if grant_type != "client_credentials":
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported_grant_type"},
        )

    expected_client_id = settings.OAUTH_CLIENT_ID or "portfolio-rag-client"
    if client_id != expected_client_id or client_secret != settings.RAG_API_KEY:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"},
        )

    access_token = create_token(client_id)
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_EXPIRY_SECONDS,
    }
