"""Query endpoints: document retrieval, keyword search, latest by type, checkpoints."""

from fastapi import APIRouter, HTTPException, Query
from app.core.index import document_index

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


@router.get("/latest/{doc_type}")
async def get_latest(doc_type: str, repo: str = None):
    """Get the latest document of a given type. Types: bootstrap, pk, intent, culture, claude, closeout, changelog."""
    doc = document_index.get_latest(doc_type, repo=repo)
    if not doc:
        detail = f"No document of type '{doc_type}'"
        if repo:
            detail += f" in repo '{repo}'"
        raise HTTPException(status_code=404, detail=detail)
    return doc.to_dict()


@router.get("/checkpoints")
async def get_checkpoints():
    """Get all checkpoint codes across all indexed documents."""
    checkpoints = document_index.get_checkpoints()
    return {"checkpoints": checkpoints, "total": len(checkpoints)}
