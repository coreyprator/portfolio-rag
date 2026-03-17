"""Query endpoints: document retrieval, keyword search, latest by type, checkpoints, document listing."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from app.core.index import document_index, compute_freshness
from app.core.vectorstore import vector_store

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


VALID_COLLECTIONS = {"portfolio", "etymology", "code", "jazz_theory", "dcc", "metapm"}


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1),
    collection: Optional[str] = None,
    n: int = 5,
    repo: Optional[str] = None,
    filetype: Optional[str] = None,
    sources: Optional[str] = None,
):
    """Semantic (ChromaDB/OpenAI) search.
    collection: 'portfolio', 'etymology', 'code', or omit for portfolio+etymology.
    repo: filter code collection by project name (e.g. 'artforge').
    filetype: filter code collection by file type (e.g. 'route', 'model', 'schema').
    sources: comma-separated source filenames to filter by (e.g. 'Beekes.pdf,Kroonen.pdf').
    """
    if collection and collection not in VALID_COLLECTIONS:
        raise HTTPException(status_code=400, detail=f"collection must be one of: {', '.join(sorted(VALID_COLLECTIONS))}")
    n = min(max(n, 1), 20)

    # Build where clause for code collection filters
    where = None
    if repo or filetype:
        if collection and collection != "code":
            raise HTTPException(status_code=400, detail="repo/filetype filters only apply to collection='code'")
        filters = []
        if repo:
            filters.append({"repo": {"$eq": repo}})
        if filetype:
            filters.append({"filetype": {"$eq": filetype}})
        where = {"$and": filters} if len(filters) > 1 else filters[0]

    # Source-level filtering (works on any collection)
    if sources:
        source_list = [s.strip() for s in sources.split(",")]
        if len(source_list) == 1:
            source_filter = {"source_file": source_list[0]}
        else:
            source_filter = {"$or": [{"source_file": s} for s in source_list]}
        # Merge with existing where if both present
        if where:
            where = {"$and": [where, source_filter]}
        else:
            where = source_filter

    results = vector_store.query(q, collection=collection, max_results=n, where=where)
    formatted = []
    for r in results:
        meta = r.get("metadata", {})
        full_text = r.get("text", "")
        entry = {
            "score": r.get("score"),
            "snippet": full_text[:500],
            "full_text": full_text,
            "source": meta.get("source_file") or meta.get("path", ""),
            "page": meta.get("page_number"),
            "section": meta.get("section") or meta.get("entry_headword", ""),
            "collection": r.get("collection"),
        }
        # Code collection extra fields
        if r.get("collection") == "code":
            entry["repo"] = meta.get("repo")
            entry["filepath"] = meta.get("filepath")
            entry["filetype"] = meta.get("filetype")
            entry["last_commit"] = meta.get("last_commit")
        formatted.append(entry)
    return {"query": q, "collection": collection or "all", "total": len(formatted), "results": formatted}


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
