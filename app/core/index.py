"""In-memory document index with keyword search."""

import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


# Exact filename -> doc_type
DOC_TYPE_MAP = {
    "PROJECT_KNOWLEDGE.md": "pk",
    "INTENT.md": "intent",
    "CULTURE.md": "culture",
    "CC_Bootstrap_Prompt.md": "bootstrap",
    "CHANGELOG.md": "changelog",
    "CLAUDE.md": "claude",
}

# Extensions -> doc_type for non-canonical files
SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".cfg"}
SCRIPT_EXTENSIONS = {".sh", ".ps1"}


def infer_doc_type(path: str) -> str:
    """Infer document type from file path and name."""
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    _, ext = os.path.splitext(filename)

    # Exact filename matches first
    if filename in DOC_TYPE_MAP:
        return DOC_TYPE_MAP[filename]

    # Content-based filename matches (handles "Harmony Lab PROJECT_KNOWLEDGE.md" etc.)
    if "PROJECT_KNOWLEDGE" in filename:
        return "pk"

    # Prefix-based matches
    if filename.startswith("SESSION_CLOSEOUT"):
        return "closeout"
    if "bootstrap" in filename.lower():
        return "bootstrap"
    if filename.startswith("INTENT"):
        return "intent"
    if filename.startswith("CC_") and ext == ".md":
        return "prompt"

    # Path-based matches
    path_lower = path.lower()
    if "/prompts/" in path_lower:
        return "prompt"
    if "migration" in path_lower:
        return "migration"
    if "template" in path_lower:
        return "template"

    # Config files (exact names)
    if filename in ("Dockerfile", ".gitignore", "Procfile") or filename.startswith(".env"):
        return "config"

    # Extension-based matches
    if ext in CONFIG_EXTENSIONS:
        return "config"
    if ext in SOURCE_EXTENSIONS:
        return "source"
    if ext in SCRIPT_EXTENSIONS:
        return "script"
    if ext == ".sql":
        return "sql"
    if ext == ".md":
        return "docs"
    if ext == ".txt":
        return "docs"

    return "other"


def extract_checkpoint(content: str) -> Optional[str]:
    m = re.search(r"<!-- CHECKPOINT:\s*(.+?)\s*-->", content)
    return m.group(1) if m else None


def extract_version(content: str) -> Optional[str]:
    for pattern in [
        r'VERSION.*?["\'](\d+\.\d+\.\d+)',
        r"v(\d+\.\d+\.\d+)",
        r"Version:\s*(\d+\.\d+\.\d+)",
    ]:
        m = re.search(pattern, content)
        if m:
            return m.group(1)
    return None


def compute_freshness(last_updated: str, stale_threshold_hours: int = 24) -> dict:
    """Compute freshness metadata for a document."""
    try:
        last = datetime.fromisoformat(last_updated)
        now = datetime.now(timezone.utc)
        age_seconds = (now - last).total_seconds()
        age_minutes = int(age_seconds / 60)
    except (ValueError, TypeError):
        return {
            "age_minutes": -1,
            "age_human": "unknown",
            "is_stale": True,
            "stale_threshold_hours": stale_threshold_hours,
        }

    if age_minutes < 60:
        age_human = f"{age_minutes} minutes ago"
    elif age_minutes < 1440:
        age_human = f"{age_minutes // 60} hours ago"
    else:
        age_human = f"{age_minutes // 1440} days ago"

    return {
        "age_minutes": age_minutes,
        "age_human": age_human,
        "is_stale": age_minutes > stale_threshold_hours * 60,
        "stale_threshold_hours": stale_threshold_hours,
    }


@dataclass
class DocumentRecord:
    repo: str
    path: str
    doc_type: str
    content: str
    checkpoint_code: Optional[str] = None
    version: Optional[str] = None
    last_updated: str = ""
    commit_sha: Optional[str] = None
    word_count: int = 0
    file_extension: str = ""
    size_bytes: int = 0

    def to_dict(self, include_content: bool = True) -> dict:
        d = asdict(self)
        if not include_content:
            d.pop("content", None)
        return d


class DocumentIndex:
    def __init__(self):
        self._docs: dict[str, DocumentRecord] = {}
        self._last_ingest: Optional[str] = None
        self._repos_indexed: set[str] = set()

    def add(self, doc: DocumentRecord):
        key = f"{doc.repo}/{doc.path}"
        self._docs[key] = doc
        self._repos_indexed.add(doc.repo)
        self._last_ingest = datetime.now(timezone.utc).isoformat()

    def get(self, repo: str, path: str) -> Optional[DocumentRecord]:
        return self._docs.get(f"{repo}/{path}")

    def search(self, query: str, repo: Optional[str] = None) -> list[dict]:
        terms = query.lower().split()
        if not terms:
            return []
        results = []
        for key, doc in self._docs.items():
            if repo and doc.repo != repo:
                continue
            content_lower = doc.content.lower()
            path_lower = doc.path.lower()
            score = sum(
                content_lower.count(term) + (10 if term in path_lower else 0)
                for term in terms
            )
            if score > 0:
                snippet = self._extract_snippet(doc.content, terms[0])
                results.append({
                    "repo": doc.repo,
                    "path": doc.path,
                    "doc_type": doc.doc_type,
                    "score": score,
                    "snippet": snippet,
                    "checkpoint_code": doc.checkpoint_code,
                    "word_count": doc.word_count,
                })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:10]

    def get_latest(self, doc_type: str, repo: Optional[str] = None) -> Optional[DocumentRecord]:
        candidates = []
        for doc in self._docs.values():
            if doc.doc_type == doc_type:
                if repo and doc.repo != repo:
                    continue
                candidates.append(doc)
        if not candidates:
            return None
        # Prefer documents with checkpoint codes, then by word count (larger = more canonical)
        candidates.sort(key=lambda d: (d.checkpoint_code is not None, d.word_count), reverse=True)
        return candidates[0]

    def get_checkpoints(self) -> dict:
        result = {}
        for doc in self._docs.values():
            if doc.checkpoint_code:
                result[doc.checkpoint_code] = {
                    "repo": doc.repo,
                    "path": doc.path,
                    "doc_type": doc.doc_type,
                }
        return result

    def list_documents(
        self,
        repo: Optional[str] = None,
        doc_type: Optional[str] = None,
        has_checkpoint: Optional[bool] = None,
        extension: Optional[str] = None,
        path_contains: Optional[str] = None,
    ) -> list[dict]:
        """List all documents matching filters. Returns metadata only (no content)."""
        results = []
        for doc in self._docs.values():
            if repo and doc.repo != repo:
                continue
            if doc_type and doc.doc_type != doc_type:
                continue
            if has_checkpoint is True and not doc.checkpoint_code:
                continue
            if has_checkpoint is False and doc.checkpoint_code:
                continue
            if extension and doc.file_extension != extension:
                continue
            if path_contains and path_contains.lower() not in doc.path.lower():
                continue
            results.append(doc.to_dict(include_content=False))
        results.sort(key=lambda d: (d["repo"], d["path"]))
        return results

    def get_all_latest(self) -> dict:
        """Get the latest document of each type across all repos.
        For per-repo types (pk, intent, etc.), returns nested by repo.
        For global types (bootstrap), returns single entry."""
        # Collect all doc_types present
        type_repo_docs: dict[str, dict[str, DocumentRecord]] = {}
        for doc in self._docs.values():
            if doc.doc_type not in type_repo_docs:
                type_repo_docs[doc.doc_type] = {}
            repo_key = doc.repo
            existing = type_repo_docs[doc.doc_type].get(repo_key)
            if existing is None or (
                (doc.checkpoint_code is not None, doc.word_count)
                > (existing.checkpoint_code is not None, existing.word_count)
            ):
                type_repo_docs[doc.doc_type][repo_key] = doc

        result = {}
        for doc_type, repo_docs in sorted(type_repo_docs.items()):
            if len(repo_docs) == 1:
                doc = list(repo_docs.values())[0]
                result[doc_type] = {
                    "repo": doc.repo,
                    "path": doc.path,
                    "checkpoint_code": doc.checkpoint_code,
                    "last_updated": doc.last_updated,
                    "word_count": doc.word_count,
                    "freshness": compute_freshness(doc.last_updated),
                }
            else:
                result[doc_type] = {}
                for repo_name, doc in sorted(repo_docs.items()):
                    result[doc_type][repo_name] = {
                        "path": doc.path,
                        "checkpoint_code": doc.checkpoint_code,
                        "last_updated": doc.last_updated,
                        "word_count": doc.word_count,
                        "freshness": compute_freshness(doc.last_updated),
                    }
        return result

    def clear_repo(self, repo: str):
        keys_to_remove = [k for k, v in self._docs.items() if v.repo == repo]
        for k in keys_to_remove:
            del self._docs[k]

    def stats(self) -> dict:
        return {
            "document_count": len(self._docs),
            "repos_indexed": sorted(self._repos_indexed),
            "last_ingest": self._last_ingest,
            "doc_types": self._count_by_type(),
        }

    def _count_by_type(self) -> dict:
        counts: dict[str, int] = {}
        for doc in self._docs.values():
            counts[doc.doc_type] = counts.get(doc.doc_type, 0) + 1
        return counts

    def _extract_snippet(self, content: str, term: str, context: int = 150) -> str:
        idx = content.lower().find(term.lower())
        if idx == -1:
            return content[:200] + "..." if len(content) > 200 else content
        start = max(0, idx - context)
        end = min(len(content), idx + len(term) + context)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet


# Global singleton
document_index = DocumentIndex()
