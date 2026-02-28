"""Query endpoints: document retrieval, keyword search, latest by type, checkpoints, document listing."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from app.core.index import document_index, compute_freshness

router = APIRouter()


@router.get("/document/{repo}/{path:path}")
async def get_document(repo: str, path: str):
    """Get full content of a specific document."""
    doc = document_index.get(repo, path)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document not found: {repo}/{path}")
    return doc.to_dict()


@router.get("/query")
async def search_documents(q: str = Query(..., min_length=1), repo: str = None):
    """Keyword search across all indexed documents."""
    results = document_index.search(q, repo=repo)
    return {"results": results, "total": len(results), "query": q}


@router.get("/latest/all")
async def get_all_latest():
    """Dashboard view: latest document of each type across all repos with freshness metadata."""
    return document_index.get_all_latest()


@router.get("/latest/{doc_type}")
async def get_latest(doc_type: str, repo: str = None):
    """Get the latest document of a given type with freshness metadata.
    Types: bootstrap, pk, intent, culture, claude, closeout, changelog, source, config, docs, etc."""
    doc = document_index.get_latest(doc_type, repo=repo)
    if not doc:
        detail = f"No document of type '{doc_type}'"
        if repo:
            detail += f" in repo '{repo}'"
        raise HTTPException(status_code=404, detail=detail)
    result = doc.to_dict()
    result["freshness"] = compute_freshness(doc.last_updated)
    return result


@router.get("/checkpoints")
async def get_checkpoints():
    """Get all checkpoint codes across all indexed documents."""
    checkpoints = document_index.get_checkpoints()
    return {"checkpoints": checkpoints, "total": len(checkpoints)}


@router.get("/documents")
async def list_documents(
    repo: Optional[str] = None,
    doc_type: Optional[str] = None,
    has_checkpoint: Optional[bool] = None,
    extension: Optional[str] = None,
    path_contains: Optional[str] = None,
):
    """Browse all indexed documents with filtering. Returns metadata only (no content)."""
    docs = document_index.list_documents(
        repo=repo,
        doc_type=doc_type,
        has_checkpoint=has_checkpoint,
        extension=extension,
        path_contains=path_contains,
    )
    # Group by repo
    repos_grouped: dict = {}
    for d in docs:
        r = d["repo"]
        if r not in repos_grouped:
            repos_grouped[r] = {"document_count": 0, "documents": []}
        repos_grouped[r]["documents"].append(d)
        repos_grouped[r]["document_count"] += 1
    return {"total": len(docs), "repos": repos_grouped}
