# Portfolio RAG -- Project Knowledge Document
<!-- CHECKPOINT: PR-PK-F7A2 -->
Generated: 2026-02-28 by CC Session
Updated: 2026-03-08 -- Sprint PR-MS4-MS1 Jazz Theory + Scheduler (v2.3.0)
Purpose: Canonical reference for all AI sessions working on this project.

### Latest Session Update -- 2026-03-12 (PR-009 MetaPM RAG Sync, v2.5.0)

- **Sprint**: PR-009 — sync MetaPM requirements into Portfolio RAG as searchable `metapm` collection
- **Current Version**: v2.5.0 — **DEPLOYED** to Cloud Run
- **Health**: `{"status":"healthy","version":"2.5.0","collections":{"portfolio":611,"etymology":1835,"code":521,"jazz_theory":17,"dcc":519,"metapm":313}}`
- **New collection**: `metapm` — 313 chunks, one per MetaPM requirement
- **Chunk ID format**: `metapm::{uuid}` (requirement UUID, not code, due to duplicate codes)
- **Chunk schema**: REQUIREMENT/PROJECT/TITLE/STATUS/PRIORITY/TYPE/PTH/DESCRIPTION/CREATED/UPDATED
- **Metadata**: source=MetaPM, code, project, status, priority, pth, version=1.0
- **Sync**: MetaPM POST /api/rag/sync triggers full re-sync (batched, replace_collection=true)
- **Cloud Scheduler**: PENDING — cc-deploy lacks `cloudscheduler.jobs.create` permission. PL must create manually:
  `gcloud scheduler jobs create http metapm-rag-sync --location=us-central1 --schedule="0 2 * * *" --uri=https://metapm.rentyourcio.com/api/rag/sync --http-method=POST --time-zone=America/Chicago --headers=Content-Type=application/json,Content-Length=0`
- **ALLOWED_CUSTOM_COLLECTIONS**: now includes `metapm`
- **VALID_COLLECTIONS**: now includes `metapm`
- **No cross-collection default**: metapm excluded from default multi-collection search (query only when `collection=metapm` specified)

### Previous: PR-MS4-MS1 Jazz Theory + Scheduler (v2.3.0)

- **Sprint**: Jazz theory collection (Collection 4) + Cloud Scheduler re-ingestion
- **Current Version**: v2.3.0 -- **DEPLOYED** to Cloud Run
- **Health**: `{"status":"healthy","version":"2.3.0","collections":{"portfolio":556,"etymology":1835,"code":521,"jazz_theory":17}}`
- **Cloud Run Revision**: portfolio-rag-00048-dsz
- **New collection**: `jazz_theory` — 17 chunks from 5 seed markdown files (ii-V-I, modes, chord subs, Jobim, standards)
- **New endpoint**: `POST /ingest/jazz_theory` — ingests seed docs from data/jazz_theory/
- **New endpoint**: `POST /admin/reingest` — token-protected trigger for scheduled re-ingestion
- **New secret**: `reingest-token` in Secret Manager (mapped to REINGEST_TOKEN env var)
- **Cloud Scheduler**: `portfolio-rag-weekly-reingest` — Sunday 3am CT, triggers /admin/reingest for portfolio collection
- **Auto-ingest**: jazz_theory collection auto-ingests on startup if empty (first deploy)
- **Cross-collection search**: omitting collection param now searches portfolio + etymology + jazz_theory

### Previous: PR-011 Code Collection (v2.2.0)

- **Sprint**: Code collection — source code semantic search across 6 repos
- **Current Version**: v2.2.0
- **Cloud Run Revision**: portfolio-rag-00044-7cn
- **New collection**: `code` — 521 files from 6 repos (.py/.sql/.js), with repo/filepath/filetype/last_commit metadata
- **New endpoint**: `POST /ingest/code` — clones repos, classifies files, embeds, upserts, backs up to GCS
- **Extended**: `/semantic` accepts `repo` and `filetype` filter params for code collection
- **Repos**: metapm(80), super-flashcards(141), artforge(70), harmonylab(35), etymython(178), portfolio-rag(17)
- **Dockerfile**: Added `git` to apt-get install

### Previous: PR-OPS-002 Fix GCS Restore (v2.1.1)

- **Sprint**: Fix GCS restore race condition on startup
- **Current Version**: v2.1.1 -- **DEPLOYED** to Cloud Run
- **Service URL**: https://portfolio-rag-57478301787.us-central1.run.app
- **Health**: `{"status":"healthy","version":"2.1.1","collections":{"portfolio":545,"etymology":1835}}`
- **Cloud Run Revision**: portfolio-rag-00041-4c4
- **Root cause**: TCP startup probe passed when gunicorn master bound to port 8080, before ASGI lifespan (GCS restore) completed. Cloud Run routed traffic to uninitialized worker.
- **Fix**:
  - Added `_ready` flag in main.py — `/health` returns 503 until lifespan startup completes
  - Switched Cloud Run startup probe from TCP to HTTP on `/health`
  - Cloud Run now waits for `/health` to return 200 before routing traffic
  - Added `exc_info=True` to GCS restore error logging
- **Startup probe config**: `httpGet.path=/health, httpGet.port=8080, period=10s, timeout=5s, failureThreshold=24`

### Previous: PR-OPS-001 GCS Persistence (v2.1.0)

- GCS backup/restore for ChromaDB — eliminates manual re-ingestion after deploys
- `chromadb.Client()` → `chromadb.PersistentClient(path="/app/chroma_data")`
- GCS backup after every ingestion: `gs://portfolio-rag-backups-57478301787/chromadb-backup/chroma_persist.tar.gz`
- GCS restore on startup: both collections available immediately after deploy
- Added `google-cloud-storage>=2.0.0` dependency

### Previous: PR-MS3 ChromaDB Semantic RAG (v2.0.0)

- Ground-up rewrite to ChromaDB + OpenAI embeddings semantic RAG engine
- EtymoRAG Lab scope absorbed: etymology collection now lives in this service
- `portfolio` collection: 545 chunks from 10 markdown files
- `etymology` collection: 1835 chunks from Beekes PDF (1853 pages)
- MCP `query_portfolio` tool with collection routing + relevance scores
- Cloud Scheduler daily re-ingestion at 8:00 UTC

### Previous: PR-MS2-FIX OAuth 2.0 (v1.1.0)

- OAuth 2.0 client_credentials grant at `POST /oauth/token`
- Bearer auth support for MCP endpoint (raw key + signed HMAC tokens)

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
| `/health` | GET | Version, per-collection counts, legacy doc count. Returns 503 during startup (gates Cloud Run HTTP probe). No auth required. |
| `/mcp` | POST | MCP Streamable HTTP (JSON-RPC 2.0). Auth: `x-api-key` or `Authorization: Bearer`. Tool: `query_portfolio(query, collection?, max_results?)` |
| `/ingest/portfolio` | POST | ChromaDB portfolio ingestion from GitHub. Auth required. |
| `/ingest/etymology` | POST | ChromaDB etymology ingestion from Beekes PDF. Auth required. |
| `/ingest/code` | POST | ChromaDB code ingestion — clones 6 repos, indexes .py/.sql/.js. Auth required. |
| `/ingest/jazz_theory` | POST | ChromaDB jazz theory ingestion from seed docs. Auth required. |
| `/admin/reingest` | POST | Trigger background re-ingestion. Auth: `X-Reingest-Token` header. Params: `?collection=portfolio\|jazz_theory`. |
| `/ingest/all` | POST | Legacy: re-ingest all repos (keyword index) |
| `/ingest/{repo}` | POST | Legacy: re-ingest specific repo |
| `/documents` | GET | Legacy: browse indexed docs with filters |
| `/latest/all` | GET | Legacy: latest doc per type |
| `/latest/{doc_type}` | GET | Legacy: latest doc of type. `?repo=` optional |
| `/document/{repo}/{path}` | GET | Legacy: full content + metadata |
| `/query?q=` | GET | Legacy: keyword search |
| `/checkpoints` | GET | Legacy: all checkpoint codes |
| `/webhook/github` | POST | GitHub push webhook with HMAC validation |
| `/prompts` | POST/GET | Prompt lifecycle management |
| `/prompts/active` | GET | Sent/in_progress prompts only |
| `/prompts/{id}` | GET/PATCH | Get or update prompt |
| `/artifacts/{sprint_id}` | POST/GET | Sprint closeout artifacts |
| `/oauth/token` | POST | OAuth 2.0 client_credentials grant |

## Schema

**Introspection URL:** https://portfolio-rag-57478301787.us-central1.run.app/openapi.json
**Framework:** FastAPI (auto-generated OpenAPI 3.x)

Phase 0 schema fetch:
```bash
curl -s https://portfolio-rag-57478301787.us-central1.run.app/openapi.json | python -c "
import sys, json
spec = json.load(sys.stdin)
paths = spec.get('paths', {})
for p in sorted(paths.keys()):
    print(p)
"
```

Key endpoint paths (update as routes change):
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /health | GET | Health check (503 until ChromaDB ready) |
| /semantic | GET | Semantic search via ChromaDB |
| /query | GET | Legacy keyword search |
| /documents | GET | List indexed documents |
| /ingest/custom | POST | Custom chunk ingestion (auth: x-api-key) |
| /ingest/code | POST | Re-ingest code repos (manual trigger) |
| /ingest/portfolio | POST | Re-ingest portfolio docs |
| /admin/reingest | POST | Background re-ingestion (X-Reingest-Token) |
| /prompts | GET, POST | Prompt lifecycle management |
| /prompts/{prompt_id} | GET, PATCH | Get or update prompt |
| /artifacts/{sprint_id} | POST, GET | Sprint closeout artifacts |
| /oauth/token | POST | OAuth 2.0 client_credentials grant |

---

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
| Runtime | Python 3.11, FastAPI, gunicorn (1 worker) + uvicorn |
| Deployment | Google Cloud Run (service: portfolio-rag, min-instances: 1, 2Gi) |
| GCP Project | super-flashcards-475210 |
| Region | us-central1 |
| Vector Store | ChromaDB PersistentClient (`/app/chroma_data`), GCS backup/restore on deploy |
| GCS Backup | `gs://portfolio-rag-backups-57478301787/chromadb-backup/chroma_persist.tar.gz` |
| Embeddings | OpenAI `text-embedding-3-small` via direct `openai.OpenAI()` client |
| Collections | `portfolio` (556 chunks), `etymology` (1835 chunks, Beekes PDF), `code` (521 files from 6 repos), `jazz_theory` (17 chunks from 5 seed docs) |
| Document Source | GitHub REST API (public repos, unauthenticated fallback if PAT expired) |
| Legacy Index | In-memory Python dict (keyword search, kept for backward compatibility) |
| MCP | Custom JSON-RPC 2.0 handler (no mcp library, direct FastAPI route) |
| Auth (MCP) | `x-api-key` header OR `Authorization: Bearer` (raw key or signed HMAC token) |
| Auth (ingestion) | Same as MCP auth (x-api-key or Bearer) |
| OAuth | HMAC-SHA256 stateless tokens. Client ID: `portfolio-rag-client`. Secret: `rag-api-key` |
| Auth (reingest) | `X-Reingest-Token` header, secret: `reingest-token` in Secret Manager |
| Re-ingestion | Cloud Scheduler: `portfolio-rag-daily-ingest` (daily 8:00 UTC, portfolio), `portfolio-rag-weekly-reingest` (Sunday 3am CT, portfolio via /admin/reingest) |
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
- **Auth**: `x-api-key` header OR `Authorization: Bearer <key>` (raw API key or signed HMAC token)
- **Tool**: `query_portfolio(query: str, collection?: str, max_results?: int = 5) -> str`
  - `collection`: `"portfolio"`, `"etymology"`, `"code"`, `"jazz_theory"`, or omit for cross-collection search (portfolio+etymology+jazz_theory)
  - `max_results`: 1-20 (default 5)
- **Return format**: `[COLLECTION: {coll} | SOURCE: {file} | {section} | score: {score}]\n<content>` per result, separated by `---`
- **Note**: cc-deploy SA cannot create secrets in Secret Manager. New secrets require cprator account.

## Collections

### Portfolio Collection (552 chunks)
- 10 markdown files from 6 repos, chunked by H2/H3 headers
- Sources: PROJECT_KNOWLEDGE.md files + governance docs (Bootstrap, CC Prompt Standard, Handoff Standard)
- Metadata: source_file, section, project, ingested_at
- Auto-ingested on cold start + daily via Cloud Scheduler

### Etymology Collection (1835 chunks)
- Beekes Etymological Dictionary of Greek (1853 pages)
- Chunked by page, metadata: page_number, entry_headword, source_file, ingested_at
- Manual trigger only: `POST /ingest/etymology`
- EtymoRAG Lab scope absorbed into this project

### Code Collection (521 files)
- Source files from 6 repos: .py, .sql, .js
- One chunk per file (truncated at 24,000 chars for embedding limits)
- Metadata: repo, filepath, filetype, last_commit, ext
- Filetype classification: route, model, schema, test, frontend, service, util
- Repos: metapm(80), super-flashcards(141), artforge(70), harmonylab(35), etymython(178), portfolio-rag(17)
- Manual trigger only: `POST /ingest/code`
- Query filters: `repo=<name>` and `filetype=<type>` via `/semantic` endpoint
- Note: `pie-network-graph` not on GitHub under coreyprator — not indexed

### Jazz Theory Collection (17 chunks)
- 5 seed markdown files in `data/jazz_theory/`: ii-V-I progressions, modes and scales, chord substitutions, Jobim harmony, common jazz standards
- Chunked by H2/H3 headers (same as portfolio), min 100 chars per chunk
- Metadata: source_file, section, project="jazz_theory", topic (from H1 heading), collection="jazz_theory", ingested_at
- Auto-ingests on startup if collection empty
- Manual trigger: `POST /ingest/jazz_theory` (auth required)
- Purpose: Powers HarmonyLab riff library feature (HL-MS4-PART-B)

### MetaPM Collection (313 chunks)
- One chunk per MetaPM requirement (all projects: HarmonyLab, MetaPM, SF, PR, PM, Etymython, EFG, ArtForge, African Safari)
- Chunk ID: `metapm::{requirement_uuid}` (UUIDs, not codes — MetaPM has duplicate codes like REQ-001)
- Content format: structured text with REQUIREMENT/PROJECT/TITLE/STATUS/PRIORITY/TYPE/PTH/DESCRIPTION/CREATED/UPDATED
- Metadata: source="MetaPM", code, project, status, priority, pth, version="1.0"
- Sync: MetaPM `POST /api/rag/sync` fetches all requirements from DB, builds chunks, POSTs to `/ingest/custom` in batches of 25 with `replace_collection=true`
- Nightly sync: Cloud Scheduler `metapm-rag-sync` at 2am CT (PENDING creation — needs PL)
- Not included in cross-collection default search; query with `collection=metapm` explicitly

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
| PR-MS4 | UI dashboard, cross-document linking, GCS-backed ChromaDB persistence |

## Deployment

```bash
# Full deploy with all secrets
gcloud run deploy portfolio-rag --source . --region us-central1 --allow-unauthenticated --project super-flashcards-475210 \
  --memory 2Gi --min-instances 1 --timeout 300 \
  --update-secrets=GITHUB_TOKEN=portfolio-rag-github-token:latest,WEBHOOK_SECRET=portfolio-rag-webhook-secret:latest,RAG_API_KEY=rag-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,OAUTH_CLIENT_ID=rag-oauth-client-id:latest,REINGEST_TOKEN=reingest-token:latest

# Trigger portfolio re-ingestion (auth required)
curl -X POST -H "x-api-key: <key>" -H "Content-Length: 0" https://portfolio-rag-57478301787.us-central1.run.app/ingest/portfolio

# Trigger etymology ingestion (auth required, ~165s)
curl -X POST -H "x-api-key: <key>" -H "Content-Length: 0" https://portfolio-rag-57478301787.us-central1.run.app/ingest/etymology

# Trigger jazz theory ingestion (auth required)
curl -X POST -H "x-api-key: <key>" -H "Content-Length: 0" https://portfolio-rag-57478301787.us-central1.run.app/ingest/jazz_theory

# Check health
curl https://portfolio-rag-57478301787.us-central1.run.app/health
```

## Known Limitations

- **ChromaDB GCS persistence**: Data backed up to GCS after ingestion, restored on startup. Health returns 503 until restore completes (HTTP startup probe). Both collections available immediately after deploy. Manual re-ingest only needed when source content changes.
- **OpenAI API key whitespace**: The `openai-api-key` secret in Secret Manager has trailing `\r\n`. Code applies `.strip()`. If replacing the secret, ensure no trailing whitespace.
- **GitHub PAT expired**: `portfolio-rag-github-token` PAT may be expired/revoked. Ingestion falls back to unauthenticated GitHub API (60 req/hr, sufficient for 10 files). Replace PAT if rate limit becomes an issue.
- **1 gunicorn worker**: Required to avoid ChromaDB data duplication. Prompt/artifact data is single-instance only.
- **Legacy endpoints**: `/documents`, `/query`, `/latest/*`, `/ingest/all` still work but use the old keyword index. Primary search is now via MCP `query_portfolio`.
- GCP_SA_KEY secret not yet configured on GitHub repo. CI/CD deploys via GitHub Actions not functional. Deploy directly with `gcloud run deploy`.
