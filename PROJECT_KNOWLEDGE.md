# Portfolio RAG -- Project Knowledge Document
<!-- CHECKPOINT: PR-PK-7D4E -->
Generated: 2026-02-28 by CC Session
Updated: 2026-03-03T15:35:00Z -- Sprint PR-MS2-FIX OAuth 2.0 (v1.1.0)
Purpose: Canonical reference for all AI sessions working on this project.

### Latest Session Update -- 2026-03-03 (PR-MS2-FIX OAuth 2.0, v1.1.0)

- **Sprint**: Add OAuth 2.0 client_credentials grant for Claude.ai connector compatibility
- **Current Version**: v1.1.0 -- **DEPLOYED** to Cloud Run
- **Service URL**: https://portfolio-rag-57478301787.us-central1.run.app
- **Health**: `{"status":"healthy","version":"1.1.0"}`
- **Cloud Run Revision**: portfolio-rag-00019-hlg
- **Changes from v1.0.0**:
  - `POST /oauth/token` endpoint: OAuth 2.0 client_credentials grant
  - Stateless HMAC-SHA256 tokens (no DB writes, no external dependencies)
  - MCP endpoint accepts `Authorization: Bearer <token>` in addition to `x-api-key`
  - Both auth paths work simultaneously (backward compatible)
  - OAuth Client ID: `portfolio-rag-client` (stored in Secret Manager as `rag-oauth-client-id`)
  - Token expiry: 3600 seconds (1 hour)

### Previous: PR-MS2 MCP Query Endpoint (v1.0.0)

- MCP Streamable HTTP endpoint at `POST /mcp` (JSON-RPC 2.0)
- `query_portfolio` tool: keyword search across all indexed docs
- API key authentication via `x-api-key` header
- `mcp` Python library for tool definition, lifespan pattern

### Previous: PR-MS2 Document Coverage + UAT Fixes (v0.2.0)

- Full-repo ingestion: ALL text files indexed (.md, .py, .html, .js, .json, .yaml, etc.)
- 14 doc_type classifications, freshness metadata, prompt lifecycle tracking
- Fixed route ordering, GitHub token whitespace, doc_type for PROJECT_KNOWLEDGE files

### Previous: PR-MS1 Portfolio RAG MVP (v0.1.0)

- MVP document retrieval service for CC sessions
- Ingested 73 canonical docs from 6 repos
- Keyword search, checkpoint extraction, webhook handler

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Version, doc count, repos indexed, doc_type counts, last ingest |
| `/documents` | GET | Browse all indexed docs with filters (repo, doc_type, has_checkpoint, extension, path_contains) |
| `/latest/all` | GET | Dashboard: latest doc per type with freshness, no content |
| `/latest/{doc_type}` | GET | Latest doc of type with freshness. `?repo=` optional |
| `/document/{repo}/{path}` | GET | Full content + metadata |
| `/query?q=` | GET | Keyword search with scored results + snippets. `?repo=` optional |
| `/checkpoints` | GET | All checkpoint codes across repos |
| `/ingest/all` | POST | Re-ingest all repos |
| `/ingest/{repo}` | POST | Re-ingest specific repo |
| `/webhook/github` | POST | GitHub push webhook with HMAC validation |
| `/prompts` | POST | Create prompt with lifecycle fields |
| `/prompts` | GET | List prompts. `?project=&status=` filters |
| `/prompts/active` | GET | Sent/in_progress prompts only |
| `/prompts/{id}` | GET | Get full prompt |
| `/prompts/{id}` | PATCH | Update status, handoff_id, uat_id, etc. |
| `/artifacts/{sprint_id}` | POST | Store closeout artifact |
| `/artifacts/{sprint_id}` | GET | Get artifacts for sprint |
| `/oauth/token` | POST | OAuth 2.0 client_credentials grant. Returns Bearer token. |
| `/mcp` | POST | MCP Streamable HTTP endpoint (JSON-RPC 2.0). Accepts `x-api-key` or `Authorization: Bearer`. Tools: `query_portfolio` |

## Doc Type Taxonomy

| doc_type | Match Rule |
|----------|-----------|
| `bootstrap` | Filename contains "Bootstrap" |
| `pk` | Filename contains "PROJECT_KNOWLEDGE" |
| `intent` | INTENT.md or INTENT_*.md |
| `culture` | CULTURE.md |
| `closeout` | SESSION_CLOSEOUT* |
| `claude` | CLAUDE.md |
| `changelog` | CHANGELOG.md |
| `prompt` | CC_*.md or in /prompts/ directory |
| `config` | .json, .yaml, .yml, .toml, .cfg, Dockerfile, .env* |
| `source` | .py, .js, .jsx, .ts, .tsx, .html, .css |
| `migration` | Path contains "migration" |
| `template` | Path contains "template" |
| `script` | .sh, .ps1 |
| `sql` | .sql |
| `docs` | .md not matching above |
| `other` | Everything else |

## Prompt Lifecycle States

```
draft -> sent -> in_progress -> completed
                                    |
                               needs_fixes -> completed_with_fixes
```

Fields tracked: status, created_at, sent_at, completed_at, handoff_id, uat_id, version_before, version_after, project, notes

## Architecture

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11, FastAPI, gunicorn + uvicorn |
| Deployment | Google Cloud Run (service: portfolio-rag) |
| GCP Project | super-flashcards-475210 |
| Region | us-central1 |
| Document Source | GitHub REST API (6 repos) |
| Index | In-memory Python dict (keyword search) |
| MCP | `mcp` Python library (FastMCP for tool definition, FastAPI for HTTP) |
| Auth (ingestion) | GitHub PAT via Secret Manager (portfolio-rag-github-token) |
| Auth (MCP endpoint) | `x-api-key` header OR `Authorization: Bearer` token (OAuth 2.0 client_credentials) |
| OAuth | HMAC-SHA256 stateless tokens. Client ID: `portfolio-rag-client`. Secret: `rag-api-key` in Secret Manager |
| CI/CD | GitHub Actions -> gcloud run deploy (needs GCP_SA_KEY secret) |

## Repos Indexed

| Repo | Owner | Doc Types Found |
|------|-------|----------------|
| project-methodology | coreyprator | pk, culture, bootstrap, claude, closeout, template, changelog, docs |
| metapm | coreyprator | pk, intent, claude, closeout, source, config, migration, sql, script |
| ArtForge | coreyprator | pk, intent, claude, source, config, migration, template, changelog |
| harmonylab | coreyprator | pk, intent, claude, source, config, docs |
| Super-Flashcards | coreyprator | pk, intent, claude, source, config, docs |
| etymython | coreyprator | pk, intent, claude, source, docs |

## MCP Integration

- **Endpoint**: `POST /mcp`
- **Protocol**: MCP Streamable HTTP (JSON-RPC 2.0)
- **Auth**: `x-api-key` header OR `Authorization: Bearer <token>` (from `/oauth/token`)
- **Tool**: `query_portfolio(query: str, n_results: int = 5) -> str`
- **Return format**: `[SOURCE: repo/path]\n<content>` per result, separated by `---`
- **Note**: cc-deploy SA cannot create secrets in Secret Manager. New secrets require cprator account.

## OAuth 2.0 (Claude.ai Connector)

- **Token Endpoint**: `POST /oauth/token`
- **Grant Type**: `client_credentials`
- **Client ID**: `portfolio-rag-client` (Secret Manager: `rag-oauth-client-id`)
- **Client Secret**: value of `rag-api-key` in Secret Manager
- **Token Method**: HMAC-SHA256 stateless (no DB, no external dependencies)
- **Token Expiry**: 3600 seconds (1 hour)
- **Claude.ai Setup**: Settings > Connectors > Add custom connector
  - URL: `https://portfolio-rag-57478301787.us-central1.run.app/mcp`
  - OAuth Client ID: `portfolio-rag-client`
  - OAuth Client Secret: [value of rag-api-key]

## Future Roadmap

| Sprint | Scope |
|--------|-------|
| PR-MS3 | ChromaDB + OpenAI embeddings, semantic search, Cloud Storage persistence |
| PR-MS4 | Beekes PDF digitization, UI dashboard, cross-document linking |

## Deployment

```bash
# Direct deploy (preserves existing secret mappings)
gcloud run deploy portfolio-rag --source . --region us-central1 --allow-unauthenticated --project super-flashcards-475210

# Deploy with all secrets (use when adding new secrets)
gcloud run deploy portfolio-rag --source . --region us-central1 --allow-unauthenticated --project super-flashcards-475210 \
  --set-secrets="GITHUB_TOKEN=portfolio-rag-github-token:latest,WEBHOOK_SECRET=portfolio-rag-webhook-secret:latest,RAG_API_KEY=rag-api-key:latest,OAUTH_CLIENT_ID=rag-oauth-client-id:latest"

# Trigger re-ingestion
curl -X POST -H "Content-Length: 0" https://portfolio-rag-57478301787.us-central1.run.app/ingest/all

# Check health
curl https://portfolio-rag-57478301787.us-central1.run.app/health
```

## Known Limitations

- In-memory index: all data lost on container restart. Auto-re-ingests on startup.
- GitHub API rate limit (5000 req/hr): ingesting 1000+ files across 6 repos can exhaust quota. Ingest repos one at a time with pauses between if full re-ingest fails. Future: batch fetches, conditional requests, or git clone. If startup ingestion fails, use `POST /ingest/all` after rate limit resets.
- GitHub PAT `portfolio-rag-github-token` in Secret Manager has `repo` scope only, not `admin:repo_hook`. Webhooks were created via `gh` CLI OAuth token. If webhooks need recreation, update PAT scope or use `gh api`.
- Starlette `Mount()` causes 307 redirects from `/path` to `/path/` with HTTP (not HTTPS) scheme behind Cloud Run's TLS termination. For MCP endpoints that need exact path matching, use direct FastAPI routes instead of mounting. Workaround applied in PR-MS2: direct FastAPI `POST /mcp` endpoint instead of `app.mount("/mcp", ...)`.
- 2 gunicorn workers = 2 separate in-memory stores. Prompt/artifact data may differ between workers.
- GCP_SA_KEY secret not yet configured on GitHub repo. CI/CD deploys via GitHub Actions not functional. Deploy directly with `gcloud run deploy`.

## MCP Library Dependencies

`mcp>=1.0.0` requires minimum versions:
- `httpx >= 0.27`
- `pydantic >= 2.7.2`
- `pydantic-settings >= 2.5.2`

Strict version pins in requirements.txt will cause build failures. When adding `mcp` to any
new service, check requirements.txt for conflicts with these minimum versions before building.
Source: PR-MS2 (2026-03-02) — strict pins caused pip resolution failures during initial build.

## Health Endpoint Enhancement (Backlog)

Current `/health` reports total document count only.
Recommended: report per-repo doc counts to make silent ingestion failures visible.
Example: `{"harmonylab": 45, "metapm": 62, "etymython": 0}`
A repo returning 0 despite being in config signals an ingestion failure.
Target sprint: PR-MS3.
