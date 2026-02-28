"""Ingestion endpoints: trigger re-indexing of repos."""

import time
import logging

from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.core.index import document_index
from app.services.github import GitHubClient

router = APIRouter()
logger = logging.getLogger(__name__)


def get_github_client() -> GitHubClient:
    return GitHubClient(token=settings.GITHUB_TOKEN, owner=settings.REPO_OWNER)


async def ingest_repo(client: GitHubClient, repo: str) -> int:
    """Ingest a single repo. Returns count of documents indexed."""
    document_index.clear_repo(repo)
    docs = await client.fetch_repo_docs(repo)
    for doc in docs:
        document_index.add(doc)
    return len(docs)


# /ingest/all must be defined BEFORE /ingest/{repo_name} to avoid path parameter capture
@router.post("/ingest/all")
async def ingest_all():
    """Re-ingest all configured repos."""
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


@router.post("/ingest/{repo_name}")
async def ingest_single(repo_name: str):
    """Re-ingest a specific repo."""
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
