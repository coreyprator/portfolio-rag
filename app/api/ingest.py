"""Ingestion endpoints: trigger re-indexing of repos and collections."""

import time
import logging

from fastapi import APIRouter, HTTPException, Header

from app.core.config import settings
from app.core.index import document_index
from app.services.github import GitHubClient
from app.services.ingestion import ingest_portfolio, ingest_etymology

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_auth(x_api_key: str | None = None, authorization: str | None = None):
    """Check auth for ingestion endpoints."""
    if not settings.RAG_API_KEY:
        return
    if x_api_key and x_api_key == settings.RAG_API_KEY:
        return
    if authorization and authorization.startswith("Bearer "):
        if authorization[7:] == settings.RAG_API_KEY:
            return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_github_client() -> GitHubClient:
    return GitHubClient(token=settings.GITHUB_TOKEN, owner=settings.REPO_OWNER)


async def ingest_repo(client: GitHubClient, repo: str) -> int:
    """Ingest a single repo into the legacy keyword index."""
    document_index.clear_repo(repo)
    docs = await client.fetch_repo_docs(repo)
    for doc in docs:
        document_index.add(doc)
    return len(docs)


# /ingest/all must be defined BEFORE /ingest/{repo_name}
@router.post("/ingest/all")
async def ingest_all():
    """Re-ingest all configured repos into the legacy keyword index."""
    client = get_github_client()
    start = time.time()
    results = []
    total = 0

    for repo in settings.REPOS:
        try:
            count = await ingest_repo(client, repo)
            results.append({"repo": repo, "documents_indexed": count})
            total += count
            logger.info(f"Ingested {repo}: {count} documents")
        except Exception as e:
            logger.error(f"Failed to ingest {repo}: {e}")
            results.append({"repo": repo, "documents_indexed": 0, "error": str(e)})

    duration = int((time.time() - start) * 1000)
    return {"repos": results, "total": total, "duration_ms": duration}


@router.post("/ingest/portfolio")
async def ingest_portfolio_endpoint(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """Ingest portfolio docs into ChromaDB portfolio collection (semantic search)."""
    _require_auth(x_api_key, authorization)
    start = time.time()
    result = await ingest_portfolio()
    duration = int((time.time() - start) * 1000)
    result["duration_ms"] = duration
    return result


@router.post("/ingest/etymology")
async def ingest_etymology_endpoint(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """Ingest Beekes PDF into ChromaDB etymology collection."""
    _require_auth(x_api_key, authorization)
    start = time.time()
    result = await ingest_etymology()
    duration = int((time.time() - start) * 1000)
    result["duration_ms"] = duration
    return result


@router.post("/ingest/{repo_name}")
async def ingest_single(repo_name: str):
    """Re-ingest a specific repo into the legacy keyword index."""
    if repo_name not in settings.REPOS:
        raise HTTPException(status_code=404, detail=f"Unknown repo: {repo_name}")

    client = get_github_client()
    start = time.time()
    count = await ingest_repo(client, repo_name)
    duration = int((time.time() - start) * 1000)

    return {
        "repo": repo_name,
        "documents_indexed": count,
        "duration_ms": duration,
    }
