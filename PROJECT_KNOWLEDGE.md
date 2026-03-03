# Portfolio RAG -- Project Knowledge Document
<!-- CHECKPOINT: PR-PK-7D4E -->
Generated: 2026-02-28 by CC Session
Updated: 2026-03-02T23:37:00Z -- Sprint PR-MS2 MCP Endpoint (v1.0.0)
Purpose: Canonical reference for all AI sessions working on this project.

### Latest Session Update -- 2026-03-02 (PR-MS2 MCP Query Endpoint, v1.0.0)

- **Sprint**: Add MCP-compatible query endpoint with API key auth
- **Current Version**: v1.0.0 -- **DEPLOYED** to Cloud Run
- **Service URL**: https://portfolio-rag-57478301787.us-central1.run.app
- **Health**: `{"status":"healthy","version":"1.0.0","documents":1265,"repos_indexed":6}`
- **Cloud Run Revision**: portfolio-rag-00016-9ln
- **Changes from v0.2.0**:
  - MCP Streamable HTTP endpoint at `POST /mcp` (JSON-RPC 2.0)
  - `query_portfolio` tool: keyword search across all indexed docs, returns results with `[SOURCE:]` labels
  - API key authentication via `x-api-key` header. Key stored in Secret Manager as `rag-api-key`
  - `mcp` Python library added for tool definition (`@mcp.tool()` decorator)
  - `search()` method accepts `limit` parameter (default 10, MCP tool uses up to 20)
  - Converted startup from `@app.on_event("startup")` to lifespan pattern
  - Relaxed dependency version pins for `mcp` compatibility (httpx>=0.27, pydantic>=2.7.2, pydantic-settings>=2.5.2)

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
| `/mcp` | POST | MCP Streamable HTTP endpoint (JSON-RPC 2.0). Requires `x-api-key` header. Tools: `query_portfolio` |

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
| Auth (MCP endpoint) | API key via Secret Manager (rag-api-key), passed as `x-api-key` header |
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
- **Auth**: `x-api-key` header. Key in Secret Manager as `rag-api-key`
- **Tool**: `query_portfolio(query: str, n_results: int = 5) -> str`
- **Return format**: `[SOURCE: repo/path]\n<content>` per result, separated by `---`
- **Phase 2**: PL manually adds MCP server URL + API key to Claude.ai Settings > Integrations
- **Note**: cc-deploy SA cannot create secrets in Secret Manager. New secrets require cprator account.

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
  --set-secrets="GITHUB_TOKEN=portfolio-rag-github-token:latest,WEBHOOK_SECRET=portfolio-rag-webhook-secret:latest,RAG_API_KEY=rag-api-key:latest"

# Trigger re-ingestion
curl -X POST -H "Content-Length: 0" https://portfolio-rag-57478301787.us-central1.run.app/ingest/all

# Check health
curl https://portfolio-rag-57478301787.us-central1.run.app/health
```

## Known Limitations

- In-memory index: all data lost on container restart. Auto-re-ingests on startup.
- GitHub API rate limit (5000 req/hr): ingesting 1000+ files can exhaust quota. If startup ingestion fails, use `POST /ingest/all` after rate limit resets.
- 2 gunicorn workers = 2 separate in-memory stores. Prompt/artifact data may differ between workers.
- GCP_SA_KEY secret not yet configured on GitHub repo. CI/CD deploys via GitHub Actions not functional. Deploy directly with `gcloud run deploy`.
