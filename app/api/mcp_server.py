"""MCP server for Portfolio RAG - query_portfolio tool backed by ChromaDB."""

import logging

from mcp.server.fastmcp import FastMCP

from app.core.vectorstore import vector_store

logger = logging.getLogger(__name__)

mcp = FastMCP("Portfolio RAG", json_response=True)


@mcp.tool()
async def query_portfolio(
    query: str,
    collection: str = None,
    max_results: int = 5,
) -> str:
    """Search the portfolio knowledge base. Returns ranked chunks with source attribution.

    Args:
        query: Natural language search query
        collection: Collection to search: 'portfolio', 'etymology', or omit for all
        max_results: Maximum chunks to return (default 5, max 20)

    Returns:
        Formatted context chunks with source, section, and relevance score
    """
    max_results = min(max(max_results, 1), 20)

    if collection and collection not in ("portfolio", "etymology"):
        return f"Unknown collection: {collection}. Valid: portfolio, etymology"

    results = vector_store.query(query, collection=collection, max_results=max_results)

    if not results:
        return f"No results found for: {query}"

    formatted_chunks = []
    for r in results:
        meta = r["metadata"]
        score = r["score"]
        coll = r["collection"]
        source = meta.get("source_file", "unknown")
        section = meta.get("section", meta.get("entry_headword", ""))

        if section:
            header = f"[COLLECTION: {coll} | SOURCE: {source} | {section} | score: {score:.2f}]"
        else:
            page = meta.get("page_number", "")
            header = f"[COLLECTION: {coll} | SOURCE: {source} | page: {page} | score: {score:.2f}]"

        text = r["text"]
        if len(text) > 2000:
            text = text[:2000] + "\n... [truncated]"

        formatted_chunks.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(formatted_chunks)
