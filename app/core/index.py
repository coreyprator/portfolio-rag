"""In-memory document index with keyword search."""

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


DOC_TYPE_MAP = {
    "PROJECT_KNOWLEDGE.md": "pk",
    "INTENT.md": "intent",
    "CULTURE.md": "culture",
    "CC_Bootstrap_Prompt.md": "bootstrap",
    "CHANGELOG.md": "changelog",
    "CLAUDE.md": "claude",
}


def infer_doc_type(path: str) -> str:
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    if filename in DOC_TYPE_MAP:
        return DOC_TYPE_MAP[filename]
    if filename.startswith("SESSION_CLOSEOUT"):
        return "closeout"
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
        for doc in self._docs.values():
            if doc.doc_type == doc_type:
                if repo and doc.repo != repo:
                    continue
                return doc
        return None

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
