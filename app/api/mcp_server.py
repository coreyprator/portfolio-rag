"""MCP server for Portfolio RAG - query_portfolio tool."""

import logging

from mcp.server.fastmcp import FastMCP

from app.core.index import document_index

logger = logging.getLogger(__name__)

mcp = FastMCP("Portfolio RAG", json_response=True)


@mcp.tool()
async def query_portfolio(query: str, n_results: int = 5) -> str:
    """
    Query the portfolio knowledge base.
    Returns relevant context from PROJECT_KNOWLEDGE.md files,
    Bootstrap standards, session closeouts, and methodology docs
    across all 10 portfolio projects.

    Args:
        query: Natural language question or keyword search
        n_results: Number of results to return (default 5, max 20)

    Returns:
        Formatted context chunks with source document labels
    """
    n_results = min(max(n_results, 1), 20)
    results = document_index.search(query, limit=n_results)

    if not results:
        return f"No results found for: {query}"

    formatted_chunks = []
    for r in results:
        doc = document_index.get(r["repo"], r["path"])
        if doc:
            content = doc.content
            if len(content) > 2000:
                content = content[:2000] + "\n... [truncated]"
            formatted_chunks.append(
                f"[SOURCE: {r['repo']}/{r['path']}]\n{content}"
            )
        else:
            formatted_chunks.append(
                f"[SOURCE: {r['repo']}/{r['path']}]\n{r.get('snippet', 'No content available')}"
            )

    return "\n\n---\n\n".join(formatted_chunks)
