# SESSION CLOSEOUT: PR-MS3
# Portfolio RAG + EtymoRAG — Unified Semantic RAG Service
# v1.1.0 → v2.0.0 | ChromaDB + OpenAI Embeddings + Multi-Collection MCP
# Date: 2026-03-03

---

## Sprint Summary

Ground-up rewrite of Portfolio RAG from keyword/filesystem search to ChromaDB + OpenAI embeddings semantic RAG engine. Absorbs EtymoRAG Lab scope into a unified multi-collection service.

## Requirements Status

| Req | Title | Status |
|-----|-------|--------|
| PR-018 | ChromaDB persistent vector store setup | DONE |
| PR-019 | Portfolio collection ingestion pipeline | DONE (527 chunks) |
| PR-020 | MCP query tool with collection routing | DONE |
| PR-021 | Re-ingestion trigger (Cloud Scheduler) | DONE (daily 8:00 UTC) |
| PR-022 | Cloud Run always-on (min-instances=1, 2Gi) | DONE |
| PR-023 | Auth — Bearer and x-api-key both accepted | DONE |
| PR-024 | Beekes PDF ingestion — etymology collection | DONE (1835 chunks from 1853 pages) |
| PR-025 | Health endpoint per-collection counts | DONE |

## Architecture Decisions

### Storage: Option B — Ephemeral + Re-ingest on Cold Start
ChromaDB runs in-memory. On container start, the portfolio collection is automatically ingested from GitHub (10 files, ~527 chunks). Etymology collection requires manual trigger via `POST /ingest/etymology` (Beekes PDF is bundled in Docker image, ingestion takes ~165 seconds).

Rationale: Option A (GCS-backed persistence) adds complexity (FUSE mounts, sync logic) for minimal gain since min-instances=1 keeps the container warm. Cold start re-ingestion takes ~30 seconds for portfolio, which is acceptable.

### Embedding Model
OpenAI `text-embedding-3-small` — called via direct `openai.OpenAI()` client, NOT ChromaDB's built-in embedding function (which had connection issues in Cloud Run due to httpx transport limitations).

### OpenAI Secret
Secret name: `openai-api-key` (shared across projects in super-flashcards-475210). **Important**: The secret value has trailing `\r\n` whitespace. The code applies `.strip()` when initializing the OpenAI client.

## Portfolio Files Ingested

| File | Project | Chunks |
|------|---------|--------|
| metapm/PROJECT_KNOWLEDGE.md | MetaPM | varies |
| project-methodology/PROJECT_KNOWLEDGE.md | project-methodology | varies |
| project-methodology/templates/CC_Bootstrap_v1.md | project-methodology | varies |
| project-methodology/docs/CAI_Outbound_CC_Prompt_Standard.md | project-methodology | varies |
| project-methodology/docs/CAI_Inbound_CC_Handoff_Standard.md | project-methodology | varies |
| ArtForge/PROJECT_KNOWLEDGE.md | ArtForge | varies |
| harmonylab/PROJECT_KNOWLEDGE.md | HarmonyLab | varies |
| Super-Flashcards/PROJECT_KNOWLEDGE.md | SuperFlashcards | varies |
| etymython/PROJECT_KNOWLEDGE.md | Etymython | varies |
| portfolio-rag/PROJECT_KNOWLEDGE.md | PortfolioRAG | varies |
| **Total** | | **527 chunks** |

## Beekes PDF Ingestion

- PDF: `698401131-Beekes-Etymological-Dictionary-Greek-1.pdf` (bundled in Docker image)
- Pages: 1853
- Chunks: 1835
- Duration: ~165 seconds
- Trigger: `POST /ingest/etymology` (auth required)

## Cloud Scheduler

- Job name: `portfolio-rag-daily-ingest`
- Schedule: `0 8 * * *` (daily 8:00 UTC / 2:00 AM CST)
- Target: `POST https://portfolio-rag-57478301787.us-central1.run.app/ingest/portfolio`
- Auth: x-api-key header with real API key (already configured)

## Cloud Run Configuration

- Revision: portfolio-rag-00026-j25
- Memory: 2Gi
- Min instances: 1
- Max instances: 20
- Timeout: 300s
- Workers: 1 (gunicorn, single worker to avoid ChromaDB data duplication)
- Startup CPU boost: enabled
- Health check start-period: 120s

## Secrets

| Secret | Purpose |
|--------|---------|
| portfolio-rag-github-token | GitHub API auth (PAT — may be expired, fallback to unauthenticated) |
| portfolio-rag-webhook-secret | GitHub webhook verification |
| rag-api-key | MCP endpoint auth |
| rag-oauth-client-id | OAuth client ID |
| openai-api-key | OpenAI embedding API (has trailing whitespace, .strip() applied) |

## Bugs Fixed During Sprint

1. **GitHub PAT expired** — All file fetches returned 403. Fix: Fallback to unauthenticated GitHub API (repos are public, 60 req/hr limit sufficient for 10 files).

2. **Duplicate chunk IDs** — Same H2/H3 header in multiple sections caused `Expected IDs to be unique`. Fix: Append enumeration index to IDs: `source_file::section::index`.

3. **ChromaDB OpenAI embedding connection error** — ChromaDB's built-in `OpenAIEmbeddingFunction` failed with `httpx.LocalProtocolError` in Cloud Run. Fix: Use direct `openai.OpenAI()` client for embedding generation.

4. **OpenAI API key whitespace** — Secret Manager value has trailing `\r\n`, causing `Illegal header value` in httpx. Fix: `settings.OPENAI_API_KEY.strip()` when creating OpenAI client.

## Smoke Test Results

### Health
```json
{"status":"healthy","version":"2.0.0","build":"unknown","collections":{"portfolio":527,"etymology":1835},"legacy_documents":1574,"repos_indexed":6}
```

### Auth Tests
- x-api-key: 200 OK
- Bearer: 200 OK
- No auth: 401

### MCP tools/list
Returns `query_portfolio` tool with query, collection (enum: portfolio/etymology), max_results parameters.

### Semantic Queries
- "MetaPM Cloud Run service name" → returns metapm-v2 from MetaPM PK.md
- "Bootstrap Phase 0 mandatory stop" → returns Phase 0 from CC_Bootstrap_v1.md
- "Greek root logos etymology" (collection=etymology) → returns λέγω/λόγος from Beekes
- "chord identification HarmonyLab" → returns Interval Priority Rule from HarmonyLab PK.md
- max_results=2 → returns exactly 2 results

## MetaPM Handoff

- Handoff ID: DFBC5BF1-296E-499A-8C59-61718314B865
- UAT ID: B67A1277-CD1F-48EB-8723-088D76FA5981
- Status: passed

## Deploy Info

- Project: super-flashcards-475210
- Service URL: https://portfolio-rag-57478301787.us-central1.run.app
- Revision: portfolio-rag-00026-j25
- Deployed by: cprator@cbsware.com

---

## PHASE 3 — Claude.ai Connector Setup (PL task):

1. Get API key:
   ```
   gcloud secrets versions access latest --secret=rag-api-key --project=super-flashcards-475210
   ```

2. Claude.ai: Settings > Connectors > Add custom connector
   Name: Portfolio RAG
   URL: https://portfolio-rag-57478301787.us-central1.run.app/mcp
   Advanced settings:
     OAuth Client ID: (leave blank)
     OAuth Client Secret: <api key from step 1>
   Click Add

3. Test in a new chat:
   "Query the portfolio for MetaPM Cloud Run service name"
   Expected: response mentions metapm-v2 with source label

4. Test etymology:
   "Search the etymology collection for the Greek root logos"
   Expected: response mentions λέγω/λόγος from Beekes dictionary

5. Trigger etymology re-ingestion if needed:
   ```
   curl -X POST https://portfolio-rag-57478301787.us-central1.run.app/ingest/etymology -H "x-api-key: <key>" -H "Content-Length: 0"
   ```
