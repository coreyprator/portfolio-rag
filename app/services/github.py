"""GitHub API client for fetching documents from portfolio repos."""

import base64
import logging
import os
from datetime import datetime, timezone

import httpx

from app.core.index import (
    DocumentRecord,
    infer_doc_type,
    extract_checkpoint,
    extract_version,
)

logger = logging.getLogger(__name__)

# Extensions to index (all text-based files)
INDEXABLE_EXTENSIONS = {
    ".md", ".py", ".html", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".txt", ".sql", ".sh", ".ps1", ".css",
}

# Exact filenames to index regardless of extension
INDEXABLE_EXACT_NAMES = {
    "Dockerfile", "Procfile", "requirements.txt", "package.json", ".gitignore",
    ".env.example",
}

# Directories to skip
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".egg-info", ".tox", ".mypy_cache",
}

# File suffixes to skip (minified, compiled)
IGNORE_SUFFIXES = (".min.js", ".min.css", ".pyc", ".whl")

# Max file size to index (500KB)
MAX_FILE_SIZE = 500_000


def is_indexable(path: str, size: int = 0) -> bool:
    """Check if a file should be indexed based on extension, name, and size."""
    if should_skip_dir(path):
        return False
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    if any(filename.endswith(s) for s in IGNORE_SUFFIXES):
        return False
    if size > MAX_FILE_SIZE:
        return False
    if filename in INDEXABLE_EXACT_NAMES:
        return True
    _, ext = os.path.splitext(filename)
    if ext in INDEXABLE_EXTENSIONS:
        return True
    return False


def should_skip_dir(path: str) -> bool:
    """Check if any path component is in the ignore list."""
    parts = path.split("/")
    return any(p in IGNORE_DIRS for p in parts)


class GitHubClient:
    def __init__(self, token: str, owner: str):
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token.strip()}"
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=30.0,
        )
        self.owner = owner

    async def fetch_repo_tree(self, repo: str) -> list[dict]:
        """Fetch the full file tree for a repo's default branch.
        Returns list of {path, size} dicts for blob items."""
        for branch in ["main", "master"]:
            resp = await self.client.get(
                f"/repos/{self.owner}/{repo}/git/trees/{branch}",
                params={"recursive": "1"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {"path": item["path"], "size": item.get("size", 0)}
                    for item in data.get("tree", [])
                    if item["type"] == "blob"
                ]
        logger.warning(f"Could not fetch tree for {repo}: {resp.status_code}")
        return []

    async def fetch_file(self, repo: str, path: str) -> tuple[str, str]:
        """Fetch a file's content and SHA from the GitHub API."""
        resp = await self.client.get(
            f"/repos/{self.owner}/{repo}/contents/{path}"
        )
        if resp.status_code != 200:
            raise ValueError(f"Failed to fetch {repo}/{path}: {resp.status_code}")
        data = resp.json()
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        sha = data.get("sha", "")
        return content, sha

    async def get_latest_commit_sha(self, repo: str) -> str:
        """Get the SHA of the latest commit on the default branch."""
        for branch in ["main", "master"]:
            resp = await self.client.get(
                f"/repos/{self.owner}/{repo}/commits/{branch}"
            )
            if resp.status_code == 200:
                return resp.json().get("sha", "")[:7]
        return ""

    async def fetch_repo_docs(self, repo: str) -> list[DocumentRecord]:
        """Fetch all indexable documents from a repo."""
        tree = await self.fetch_repo_tree(repo)
        indexable = [item for item in tree if is_indexable(item["path"], item["size"])]

        if not indexable:
            logger.info(f"No indexable documents found in {repo}")
            return []

        commit_sha = await self.get_latest_commit_sha(repo)
        now = datetime.now(timezone.utc).isoformat()
        docs = []

        for item in indexable:
            path = item["path"]
            size = item["size"]
            try:
                content, file_sha = await self.fetch_file(repo, path)
                filename = path.rsplit("/", 1)[-1] if "/" in path else path
                _, ext = os.path.splitext(filename)
                doc = DocumentRecord(
                    repo=repo,
                    path=path,
                    doc_type=infer_doc_type(path),
                    content=content,
                    checkpoint_code=extract_checkpoint(content),
                    version=extract_version(content),
                    last_updated=now,
                    commit_sha=commit_sha,
                    word_count=len(content.split()),
                    file_extension=ext if ext else filename,
                    size_bytes=size,
                )
                docs.append(doc)
                logger.info(f"Indexed {repo}/{path} ({doc.word_count} words, type={doc.doc_type})")
            except Exception as e:
                logger.error(f"Failed to fetch {repo}/{path}: {e}")

        return docs
