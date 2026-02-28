"""GitHub webhook handler for automatic re-ingestion on push."""

import hmac
import hashlib
import logging

from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.api.ingest import get_github_client, ingest_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub push webhook. Validates signature, triggers re-ingestion."""
    if settings.WEBHOOK_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        body = await request.body()
        expected = "sha256=" + hmac.new(
            settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    repo_name = payload.get("repository", {}).get("name", "")

    if not repo_name:
        return {"status": "ignored", "reason": "no repository name in payload"}

    if repo_name not in settings.REPOS:
        return {"status": "ignored", "reason": f"repo '{repo_name}' not in configured repos"}

    ref = payload.get("ref", "")
    if ref and ref not in ("refs/heads/main", "refs/heads/master"):
        return {"status": "ignored", "reason": f"push to non-default branch: {ref}"}

    client = get_github_client()
    try:
        count = await ingest_repo(client, repo_name)
        logger.info(f"Webhook re-ingested {repo_name}: {count} documents")
        return {"status": "ingested", "repo": repo_name, "documents_indexed": count}
    except Exception as e:
        logger.error(f"Webhook ingestion failed for {repo_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
