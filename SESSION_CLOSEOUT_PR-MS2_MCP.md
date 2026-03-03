# SESSION CLOSEOUT -- PR-MS2 MCP Query Endpoint

**Sprint**: PR-MS2 (MCP Endpoint)
**Date**: 2026-03-02
**Project**: Portfolio RAG
**Version**: v0.2.0 -> v1.0.0
**Bootstrap**: v1.4.4 (BOOT-1.4.4-7F2C)

## Deliverables

| # | Deliverable | Status | Evidence |
|---|-------------|--------|----------|
| 1 | MCP server with query_portfolio tool (PR-011) | PASS | `tools/list` returns tool schema, `tools/call` returns results with [SOURCE:] labels |
| 2 | API key auth via Secret Manager (PR-012) | PASS | No key: 401. Wrong key: 401. Correct key: 200. Secret: `rag-api-key` |
| 3 | Deploy to Cloud Run + smoke tests (PR-013) | PASS | Revision `portfolio-rag-00016-9ln`, all 6 smoke tests passed |
| 4 | Phase 2 Claude.ai setup instructions (PR-014) | PASS | See below |

## Smoke Test Results

```
Test 1: Health check (no auth)
  {"status":"healthy","version":"1.0.0","documents":1265,"repos_indexed":6}

Test 2: POST /mcp without key
  HTTP 401: {"error":"Invalid or missing API key"}

Test 3: POST /mcp with wrong key
  HTTP 401: {"error":"Invalid or missing API key"}

Test 4: tools/list with valid key
  HTTP 200: {"tools":[{"name":"query_portfolio",...}]}

Test 5: tools/call "HarmonyLab chord identification" n_results=3
  HTTP 200: 3 results from harmonylab/song.html, HL PK.md, chords.py

Test 6: initialize
  HTTP 200: {"serverInfo":{"name":"Portfolio RAG","version":"1.0.0"}} (74ms)
```

## Files Changed

| File | Change |
|------|--------|
| `app/api/mcp_server.py` | NEW - FastMCP server with query_portfolio tool |
| `app/api/mcp_endpoint.py` | NEW - FastAPI POST /mcp JSON-RPC handler with auth |
| `app/api/mcp_auth.py` | NEW - ASGI auth middleware (created but not used in final approach) |
| `app/core/config.py` | Added RAG_API_KEY setting, version bump 0.2.0 -> 1.0.0 |
| `app/core/index.py` | Added `limit` parameter to `search()` method |
| `app/main.py` | Converted to lifespan pattern, added MCP endpoint router |
| `requirements.txt` | Added `mcp>=1.0.0`, relaxed dependency version pins for compatibility |

## Architecture Decisions

1. **Direct FastAPI endpoint instead of ASGI mount**: The MCP SDK's `streamable_http_app()` + `app.mount()` caused a 307 redirect from `/mcp` to `/mcp/`. Fixed by implementing the MCP JSON-RPC protocol as a regular FastAPI POST endpoint. The `mcp` library is used for tool definition (`@mcp.tool()`) while the HTTP layer is handled by FastAPI directly.

2. **API key auth pattern**: `x-api-key` header checked in the endpoint handler. Key stored in Secret Manager as `rag-api-key`, mapped to `RAG_API_KEY` env var on Cloud Run via `--set-secrets`.

3. **Keyword search (not ChromaDB)**: The sprint prompt references "ChromaDB query logic" but the current index is in-memory keyword search. ChromaDB is roadmapped for PR-MS3. The MCP tool wraps `document_index.search()`.

4. **Dependency version relaxation**: `mcp>=1.0.0` requires `httpx>=0.27`, `pydantic>=2.7.2`, `pydantic-settings>=2.5.2`. Relaxed the strict pins to allow pip to resolve compatible versions.

## Service Configuration

| Setting | Value |
|---------|-------|
| Service URL | https://portfolio-rag-57478301787.us-central1.run.app |
| MCP Endpoint | POST /mcp |
| Cloud Run Revision | portfolio-rag-00016-9ln |
| Auth Header | x-api-key |
| Secret Manager Key | rag-api-key |

## Phase 2: Claude.ai MCP Setup (PL manual step)

1. Retrieve API key from Secret Manager:
   ```
   gcloud secrets versions access latest --secret=rag-api-key --project=super-flashcards-475210
   ```

2. In Claude.ai: Settings > Integrations > Add MCP Server

3. Server URL:
   ```
   https://portfolio-rag-57478301787.us-central1.run.app/mcp
   ```

4. Auth: Custom header
   - Header name: x-api-key
   - Header value: [key from step 1]

5. Test: Ask Claude "query portfolio for HarmonyLab chord identification"
   Expected: response draws from HL PK.md context

## MetaPM

- **Handoff ID**: 3FADF916-02F4-4061-8C92-75E054D60D45
- **UAT ID**: B29C4E99-BE4B-48EE-9A89-B5B0499E57ED
- **Handoff URL**: https://metapm.rentyourcio.com/mcp/handoffs/3FADF916-02F4-4061-8C92-75E054D60D45/content

## Known Issues

1. **mcp_auth.py unused**: Created an ASGI middleware file but the final implementation uses direct endpoint auth instead. File can be deleted in a cleanup sprint.
2. **GitHub API rate limit**: Was exhausted at session start (5000/5000). Reset at 6:03 PM CST. Ingestion succeeded on final deploy (1265 docs).
3. **INTENT.md missing checkpoint**: Portfolio RAG's INTENT.md has no `<!-- CHECKPOINT: ... -->` line. Should be added.

## Lessons Learned

1. **BOOTSTRAP**: Starlette `Mount()` generates 307 redirects from `/path` to `/path/` with HTTP (not HTTPS) scheme behind Cloud Run's TLS termination. For MCP endpoints that need exact path matching, use direct FastAPI routes instead of mounting.
2. **PROJECT**: The `mcp>=1.0.0` package requires `httpx>=0.27`, `pydantic>=2.7.2`, `pydantic-settings>=2.5.2`. Strict version pins in requirements.txt will cause build failures. Document minimum versions in PK.md.
3. **PROJECT**: cc-deploy SA lacks `secretmanager.secrets.create` permission. Creating new secrets requires cprator account. Document this constraint in PK.md.

## PM-005 (Parallel Task)

Completed PM-005 (GitHub PAT rate limit diagnosis) in parallel. Root cause: GitHub API core rate limit exhausted (5000/5000). Git operations unaffected. PM-006 lesson applies not blocked. SESSION_CLOSEOUT.md committed to project-methodology (`a112839`).
