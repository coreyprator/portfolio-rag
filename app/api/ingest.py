"""Ingestion endpoints: trigger re-indexing of repos and collections."""

import os
import subprocess
import tempfile
import time
import logging

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.core.config import settings
from app.core.index import document_index
from app.core.vectorstore import backup_to_gcs, vector_store
from app.services.github import GitHubClient
from app.services.ingestion import ingest_portfolio, ingest_etymology, ingest_jazz_theory

# Repos to clone for code collection (repo key → GitHub path)
CODE_REPOS = [
    {"name": "metapm",           "repo": "coreyprator/metapm"},
    {"name": "super-flashcards", "repo": "coreyprator/Super-Flashcards"},
    {"name": "artforge",         "repo": "coreyprator/ArtForge"},
    {"name": "harmonylab",       "repo": "coreyprator/HarmonyLab"},
    {"name": "etymython",        "repo": "coreyprator/etymython"},
    {"name": "portfolio-rag",    "repo": "coreyprator/portfolio-rag"},
    # pie-network-graph not on GitHub — skipped
]

CODE_EXTENSIONS = {".py", ".sql", ".js"}

CODE_EXCLUDE = [
    "__pycache__", ".pyc", "node_modules", "venv", ".venv",
    "static/vendor", "static/libs", "dist/", ".git/",
]

# Max chars per file to embed (OpenAI 8191-token limit; ~4 chars/token)
MAX_FILE_CHARS = 24000


def _classify_filetype(filepath: str, content: str) -> str:
    p = filepath.lower().replace("\\", "/")
    if "/routes/" in p or "/routers/" in p or "@app.get" in content or "@app.post" in content or "@router." in content:
        return "route"
    if "/models/" in p or "class.*Base" in content or "SQLModel" in content:
        return "model"
    if "/migrations/" in p or p.endswith(".sql"):
        return "schema"
    if "/tests/" in p or "/test_" in p or p.startswith("test_"):
        return "test"
    if ("/static/" in p or "/templates/" in p) and p.endswith(".js"):
        return "frontend"
    if "/services/" in p:
        return "service"
    return "util"


def _get_commit_date(clone_dir: str, filepath: str) -> str:
    r = subprocess.run(
        ["git", "-C", clone_dir, "log", "-1", "--format=%ai", "--", filepath],
        capture_output=True, text=True, timeout=10
    )
    return r.stdout.strip()[:10] or "unknown"

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
    backup_to_gcs()
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
    backup_to_gcs()
    return result


@router.post("/ingest/jazz_theory")
async def ingest_jazz_theory_endpoint(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """Ingest jazz theory seed docs into ChromaDB jazz_theory collection."""
    _require_auth(x_api_key, authorization)
    start = time.time()
    result = await ingest_jazz_theory()
    duration = int((time.time() - start) * 1000)
    result["duration_ms"] = duration
    backup_to_gcs()
    return result


@router.post("/ingest/code")
async def ingest_code(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """Clone all configured repos and index source files into the 'code' ChromaDB collection."""
    _require_auth(x_api_key, authorization)
    start = time.time()

    docs, metadatas, ids = [], [], []
    repo_stats = []
    skipped_repos = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for repo_cfg in CODE_REPOS:
            repo_name = repo_cfg["name"]
            repo_url = f"https://github.com/{repo_cfg['repo']}.git"
            clone_dir = os.path.join(tmpdir, repo_name)

            result = subprocess.run(
                ["git", "clone", "--depth=1", repo_url, clone_dir],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.warning(f"Failed to clone {repo_url}: {result.stderr[:200]}")
                skipped_repos.append(repo_name)
                continue

            file_count = 0
            for root, dirs, files in os.walk(clone_dir):
                rel_root = os.path.relpath(root, clone_dir).replace("\\", "/")
                # Prune excluded dirs
                dirs[:] = [d for d in dirs if not any(ex in os.path.join(rel_root, d) for ex in CODE_EXCLUDE)]

                for fname in files:
                    ext = os.path.splitext(fname)[1]
                    if ext not in CODE_EXTENSIONS:
                        continue

                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, clone_dir).replace("\\", "/")

                    if any(ex in rel_path for ex in CODE_EXCLUDE):
                        continue

                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    except Exception:
                        continue

                    if not content.strip() or len(content) < 50:
                        continue

                    # Truncate large files to stay within embedding limits
                    if len(content) > MAX_FILE_CHARS:
                        content = content[:MAX_FILE_CHARS] + "\n# [truncated]"

                    filetype = _classify_filetype(rel_path, content)
                    commit_date = _get_commit_date(clone_dir, rel_path)

                    # Metadata header prepended for richer embedding context
                    doc = f"# repo:{repo_name} file:{rel_path} type:{filetype}\n\n{content}"

                    doc_id = f"{repo_name}::{rel_path}"
                    docs.append(doc)
                    metadatas.append({
                        "repo":        repo_name,
                        "filepath":    rel_path,
                        "filetype":    filetype,
                        "last_commit": commit_date,
                        "ext":         ext,
                    })
                    ids.append(doc_id)
                    file_count += 1

            repo_stats.append({"repo": repo_name, "files": file_count})
            logger.info(f"Code ingest: {repo_name} — {file_count} files")

    if not docs:
        raise HTTPException(status_code=500, detail="No files indexed — all repos failed or empty")

    # Upsert into "code" collection (replaces by id so this is idempotent)
    total = vector_store.upsert("code", ids=ids, documents=docs, metadatas=metadatas)
    backup_to_gcs()

    duration = int((time.time() - start) * 1000)
    return {
        "status": "ok",
        "total_files": total,
        "repos": repo_stats,
        "skipped_repos": skipped_repos,
        "duration_ms": duration,
    }


class CustomChunk(BaseModel):
    id: str
    content: str
    metadata: dict = {}


class CustomIngestRequest(BaseModel):
    collection: str
    chunks: list[CustomChunk]
    replace_collection: bool = False


ALLOWED_CUSTOM_COLLECTIONS = {"dcc", "portfolio", "etymology", "jazz_theory", "metapm", "wiktionary"}


@router.post("/ingest/custom")
async def ingest_custom(
    body: CustomIngestRequest,
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
):
    """Ingest arbitrary chunks into a named ChromaDB collection.

    Accepts: collection name, list of {id, content, metadata} chunks.
    If replace_collection=True, wipes the collection before ingesting.
    Auth: same x-api-key as other ingest endpoints.
    """
    _require_auth(x_api_key, authorization)

    if body.collection not in ALLOWED_CUSTOM_COLLECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"collection must be one of: {', '.join(sorted(ALLOWED_CUSTOM_COLLECTIONS))}"
        )

    start = time.time()

    if body.replace_collection:
        vector_store.delete_collection(body.collection)

    ids = [c.id for c in body.chunks]
    documents = [c.content for c in body.chunks]
    metadatas = [c.metadata for c in body.chunks]

    total = vector_store.upsert(body.collection, ids=ids, documents=documents, metadatas=metadatas)
    backup_to_gcs()

    duration = int((time.time() - start) * 1000)
    return {
        "collection": body.collection,
        "chunks_ingested": total,
        "status": "success",
        "duration_ms": duration,
    }


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
