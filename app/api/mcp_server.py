"""MCP server for Portfolio RAG - tools backed by ChromaDB."""

import logging

from mcp.server.fastmcp import FastMCP

from app.core.vectorstore import vector_store

logger = logging.getLogger(__name__)

mcp = FastMCP("Portfolio RAG", json_response=True)

# MP48 TSK-005: 'code' is no longer a valid collection here. Source code is
# authoritative in MetaPM's SQL code_files table. MCP callers get a deprecation
# error instead of a silent empty result.
VALID_COLLECTIONS = {"portfolio", "etymology", "jazz_theory", "dcc", "metapm"}

_CODE_DEPRECATION_MSG = (
    "The 'code' collection is deprecated. Use MetaPM SQL code_files via the "
    "execute_sql_query MCP tool (database=MetaPM, sql=\"SELECT * FROM code_files "
    "WHERE app = ?\"), or GET https://metapm.rentyourcio.com/api/code-files/status."
)


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

    if collection == "code":
        return _CODE_DEPRECATION_MSG
    if collection and collection not in ("portfolio", "etymology"):
        return f"Unknown collection: {collection}. Valid: portfolio, etymology"

    results = vector_store.query(query, collection=collection, max_results=max_results)

    if not results:
        return f"No results found for: {query}"

    return _format_results(results)


@mcp.tool()
async def rag_query(
    query: str,
    collection: str = "portfolio",
    n: int = 5,
) -> str:
    """Semantic search across Portfolio RAG vector database.
    Use to retrieve canonical standards documents, Bootstrap sections,
    PROJECT_KNOWLEDGE.md content, CAI standards, and methodology docs.
    Always use this before writing CC prompts to verify current standards.

    Args:
        query: Natural language search query
        collection: Collection to search. Options: portfolio (methodology/standards),
            metapm (requirements), etymology (Beekes dictionary), dcc (Greek core vocab),
            jazz_theory (jazz harmony). For source code, use the MetaPM execute_sql_query
            MCP tool against the code_files table — the ChromaDB 'code' collection is
            deprecated (MP48 TSK-005).
        n: Number of results to return (default 5, max 20)

    Returns:
        Formatted context chunks with source, section, and relevance score
    """
    n = min(max(n, 1), 20)

    if collection == "code":
        return _CODE_DEPRECATION_MSG
    if collection and collection not in VALID_COLLECTIONS:
        return f"Unknown collection: {collection}. Valid: {', '.join(sorted(VALID_COLLECTIONS))}"

    results = vector_store.query(query, collection=collection, max_results=n)

    if not results:
        return f"No results found for: {query}"

    return _format_results(results)


@mcp.tool()
async def rag_get_document(
    source: str,
    collection: str = "portfolio",
) -> str:
    """Retrieve all chunks from a specific document in Portfolio RAG.
    Use when rag_query returns a snippet and you need the full document.
    Source paths follow the pattern: project/filename.md
    Examples: project-methodology/docs/CAI_Outbound_CC_Prompt_Standard.md,
    harmonylab/PROJECT_KNOWLEDGE.md, metapm/PROJECT_KNOWLEDGE.md

    Args:
        source: Document source path as returned by rag_query
        collection: Collection to search (default: portfolio)

    Returns:
        All chunks from the specified document, ordered by section/page
    """
    if collection == "code":
        return _CODE_DEPRECATION_MSG
    if collection and collection not in VALID_COLLECTIONS:
        return f"Unknown collection: {collection}. Valid: {', '.join(sorted(VALID_COLLECTIONS))}"

    where = {"source_file": {"$eq": source}}
    results = vector_store.query_by_metadata(
        collection=collection, where=where, limit=50
    )

    if not results:
        return f"No chunks found for source: {source} in collection: {collection}"

    return _format_results(results)


def _format_results(results: list) -> str:
    """Format ChromaDB results into readable text for MCP responses."""
    formatted_chunks = []
    for r in results:
        meta = r.get("metadata", {})
        score = r.get("score")
        coll = r.get("collection", "")
        source = meta.get("source_file", meta.get("path", "unknown"))
        section = meta.get("section", meta.get("entry_headword", ""))

        if section:
            header = f"[COLLECTION: {coll} | SOURCE: {source} | {section}"
        else:
            page = meta.get("page_number", "")
            header = f"[COLLECTION: {coll} | SOURCE: {source} | page: {page}"

        if score is not None:
            header += f" | score: {score:.2f}]"
        else:
            header += "]"

        text = r.get("text", "")
        if len(text) > 2000:
            text = text[:2000] + "\n... [truncated]"

        formatted_chunks.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(formatted_chunks)
