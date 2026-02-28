"""GitHub API client for fetching canonical documents."""

import base64
import logging
from datetime import datetime, timezone

import httpx

from app.core.index import (
    DocumentRecord,
    infer_doc_type,
    extract_checkpoint,
    extract_version,
)

logger = logging.getLogger(__name__)

CANONICAL_FILES = {
    "PROJECT_KNOWLEDGE.md",
    "INTENT.md",
    "CULTURE.md",
    "CC_Bootstrap_Prompt.md",
    "CHANGELOG.md",
    "CLAUDE.md",
}

CANONICAL_PREFIXES = ["SESSION_CLOSEOUT", "CC_Bootstrap"]

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def is_canonical(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    if filename in CANONICAL_FILES:
        return True
    for prefix in CANONICAL_PREFIXES:
        if filename.startswith(prefix) and filename.endswith(".md"):
            return True
    return False


def should_skip_dir(path: str) -> bool:
    parts = path.split("/")
    return any(p in IGNORE_DIRS for p in parts)


class GitHubClient:
    def __init__(self, token: str, owner: str):
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=30.0,
        )
        self.owner = owner

    async def fetch_repo_tree(self, repo: str) -> list[str]:
        """Fetch the full file tree for a repo's default branch."""
        # Try main first, fall back to master
        for branch in ["main", "master"]:
            resp = await self.client.get(
                f"/repos/{self.owner}/{repo}/git/trees/{branch}",
                params={"recursive": "1"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    item["path"]
                    for item in data.get("tree", [])
                    if item["type"] == "blob" and not should_skip_dir(item["path"])
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

    async def fetch_canonical_docs(self, repo: str) -> list[DocumentRecord]:
        """Fetch all canonical documents from a repo."""
        tree = await self.fetch_repo_tree(repo)
        canonical_paths = [p for p in tree if is_canonical(p)]

        if not canonical_paths:
            logger.info(f"No canonical documents found in {repo}")
            return []

        commit_sha = await self.get_latest_commit_sha(repo)
        now = datetime.now(timezone.utc).isoformat()
        docs = []

        for path in canonical_paths:
            try:
                content, file_sha = await self.fetch_file(repo, path)
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
                )
                docs.append(doc)
                logger.info(f"Indexed {repo}/{path} ({doc.word_count} words, type={doc.doc_type})")
            except Exception as e:
                logger.error(f"Failed to fetch {repo}/{path}: {e}")

        return docs
