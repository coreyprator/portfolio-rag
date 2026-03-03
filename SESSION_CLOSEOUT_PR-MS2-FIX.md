# SESSION CLOSEOUT -- PR-MS2-FIX OAuth 2.0 for Claude.ai Connector

**Sprint**: PR-MS2-FIX
**Date**: 2026-03-03
**Project**: Portfolio RAG
**Version**: v1.0.0 -> v1.1.0
**Bootstrap**: v1.4.4 (BOOT-1.4.4-7F2C)

## Deliverables

| # | Deliverable | Status | Evidence |
|---|-------------|--------|----------|
| 1 | POST /oauth/token with client_credentials grant (PR-016) | PASS | Valid creds -> access_token. Wrong secret -> 400 invalid_client. Wrong grant_type -> 400 unsupported. |
| 2 | MCP accepts Bearer token (PR-017) | PASS | Bearer token -> tools/list OK. x-api-key still works (regression). No auth -> 401. |

## Smoke Test Results

```
Test 1: Health check (no auth)
  {"status":"healthy","version":"1.1.0","documents":404,"repos_indexed":2}

Test 2: POST /oauth/token with valid creds
  {"access_token":"eyJzdW...","token_type":"Bearer","expires_in":3600}

Test 3: POST /oauth/token with wrong secret
  {"error":"invalid_client"}

Test 4: POST /oauth/token with wrong grant_type
  {"error":"unsupported_grant_type"}

Test 5: POST /mcp with no auth
  HTTP 401: {"error":"Invalid or missing API key"}

Test 6: POST /mcp with Bearer token
  HTTP 200: {"tools":[{"name":"query_portfolio",...}]}

Test 7: POST /mcp with x-api-key (regression)
  HTTP 200: {"tools":[{"name":"query_portfolio",...}]}
```

## Files Changed

| File | Change |
|------|--------|
| `app/api/oauth.py` | NEW - OAuth 2.0 `/oauth/token` endpoint with HMAC-SHA256 stateless tokens |
| `app/api/mcp_endpoint.py` | MODIFIED - `_check_auth()` accepts both `x-api-key` and `Authorization: Bearer` |
| `app/core/config.py` | MODIFIED - VERSION 1.0.0 -> 1.1.0, added OAUTH_CLIENT_ID setting |
| `app/main.py` | MODIFIED - Added oauth router, updated endpoint listing |

## Architecture Decisions

1. **Stateless HMAC-SHA256 tokens**: No JWT library dependency needed. Token format: `base64url(payload).base64url(hmac-sha256(payload, RAG_API_KEY))`. Payload contains `sub`, `iat`, `exp`. Verified by recomputing HMAC and checking expiry. No DB writes per token request.

2. **Dual auth paths**: `_check_auth()` tries x-api-key first, then Bearer token. Either succeeding grants access. This keeps backward compatibility with direct API key usage while enabling Claude.ai's OAuth flow.

3. **Static Client ID**: `portfolio-rag-client` stored in Secret Manager as `rag-oauth-client-id`. Mapped to `OAUTH_CLIENT_ID` env var on Cloud Run. Falls back to hardcoded `portfolio-rag-client` if env var not set.

## Service Configuration

| Setting | Value |
|---------|-------|
| Service URL | https://portfolio-rag-57478301787.us-central1.run.app |
| OAuth Endpoint | POST /oauth/token |
| MCP Endpoint | POST /mcp |
| Cloud Run Revision | portfolio-rag-00019-hlg |
| Auth (MCP) | x-api-key header OR Authorization: Bearer token |
| OAuth Client ID | portfolio-rag-client |
| OAuth Client Secret | [value of rag-api-key in Secret Manager] |
| Token Expiry | 3600 seconds (1 hour) |
| New Secret | rag-oauth-client-id = "portfolio-rag-client" |

## PL CONNECTOR SETUP after v1.1.0 deploys

1. Get key:
   ```
   gcloud secrets versions access latest --secret=rag-api-key --project=super-flashcards-475210
   ```

2. Claude.ai: Settings > Connectors > Add custom connector
   - Name: Portfolio RAG
   - URL: https://portfolio-rag-57478301787.us-central1.run.app/mcp
   - Advanced settings:
     - OAuth Client ID: portfolio-rag-client
     - OAuth Client Secret: [key from step 1]
   - Click Add

3. Claude.ai calls /oauth/token automatically. If connected, tools appear in chat.

## MetaPM

- **Handoff ID**: B1D65AD6-A7E0-4C75-A745-0251C2D8DC51
- **UAT ID**: 41AD6EDE-6658-4BD8-B1A9-756E719E2941
- **Handoff URL**: https://metapm.rentyourcio.com/mcp/handoffs/B1D65AD6-A7E0-4C75-A745-0251C2D8DC51/content

## Known Issues

1. **Health shows 404 docs / 2 repos**: Startup ingestion partially failed (GitHub API rate limit). Not related to this sprint. Use `POST /ingest/all` after rate limit resets.
2. **MetaPM requirement seeds failed**: No `proj-pr` project in MetaPM. PR-016 and PR-017 not seeded. Same issue as PR-MS2.
3. **mcp_auth.py still unused**: Created in PR-MS2, still not used. Cleanup candidate.

## Lessons Learned

1. **PROJECT**: OAuth 2.0 `client_credentials` flow can be implemented with zero external dependencies using Python's `hmac`, `hashlib`, `json`, `base64`, `time` stdlib modules. No need for PyJWT.
2. **PROJECT**: Claude.ai Connectors UI sends `application/x-www-form-urlencoded` body to `/oauth/token`, not JSON. Must parse URL-encoded form data.
3. **PROJECT**: MetaPM's `requirements` API uses `priority: P1|P2|P3` and `status: backlog|draft|...` enums (not P0 or in-progress). Sprint prompts should use valid enum values.
