# SESSION CLOSEOUT: PR-OPS-001
# Portfolio RAG — Beekes GCS Persistence (PR-010)
# v2.0.0 → v2.1.0
# Date: 2026-03-06

---

## Sprint Summary

Eliminated the operational liability of manual Beekes re-ingestion after every deploy. ChromaDB now persists to disk via `PersistentClient` and backs up to GCS after every ingestion. On startup, the backup is restored automatically — both portfolio (545 chunks) and etymology (1835 chunks) are available immediately.

## Changes

### vectorstore.py
- `chromadb.Client()` → `chromadb.PersistentClient(path="/app/chroma_data")`
- Added `backup_to_gcs()`: tars persist directory, uploads to GCS
- Added `restore_from_gcs()`: downloads from GCS, extracts to persist directory

### main.py
- Startup: call `restore_from_gcs()` before `vector_store.initialize()`
- If both collections populated from backup, skip portfolio re-ingestion
- If portfolio empty (first deploy, no backup), ingest from GitHub

### ingest.py
- `POST /ingest/portfolio` and `POST /ingest/etymology` both call `backup_to_gcs()` after ingestion

### Dockerfile
- Added `mkdir -p /app/chroma_data` before user creation (writable by appuser)

### requirements.txt
- Added `google-cloud-storage>=2.0.0`

### config.py
- VERSION: 2.0.0 → 2.1.0

## GCS Configuration

| Item | Value |
|------|-------|
| Bucket | `gs://portfolio-rag-backups-57478301787` |
| Location | us-central1 |
| Blob path | `chromadb-backup/chroma_persist.tar.gz` |
| Backup size | ~38.9 MiB |
| IAM | `57478301787-compute@developer.gserviceaccount.com` + `cc-deploy@...` = objectAdmin |

## Verification

1. First deploy (no backup): portfolio ingested from GitHub (545 chunks), etymology=0 (expected)
2. Manual `POST /ingest/etymology`: 1835 chunks, backup created in GCS
3. Manual `POST /ingest/portfolio`: 545 chunks, backup updated in GCS
4. **Second deploy (revision 00037-ntn)**: both collections restored from GCS automatically
5. Immediate query for "etymology of cosmos" → returned κόσμος from Beekes ✅

## Acceptance Criteria

- [x] GCS bucket exists with backup blob after ingestion
- [x] Fresh deploy restores Beekes data automatically — no manual curl needed
- [x] Semantic query for "cosmos" returns κόσμος immediately after deploy
- [x] Manual `/ingest/etymology` endpoint still works
- [x] Health endpoint only returns 200 after restore completes

## Deploy Info

- Revision: portfolio-rag-00037-ntn
- Service URL: https://portfolio-rag-57478301787.us-central1.run.app
- Health: `{"status":"healthy","version":"2.1.0","collections":{"portfolio":545,"etymology":1835}}`

## MetaPM Handoff

- Handoff ID: FF244361-9B27-4CD4-9352-4946FC0C4241
- UAT ID: ECEDE4E2-0B24-4127-ACF9-22AA560A9DE8
- Status: passed

## When to Manually Re-ingest

- **Portfolio**: Automatic daily via Cloud Scheduler. Manual: `POST /ingest/portfolio` (after PK.md updates)
- **Etymology**: Only when Beekes PDF content changes. Manual: `POST /ingest/etymology`
- Both endpoints update the GCS backup, so subsequent deploys get the latest data.
