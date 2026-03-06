# SESSION CLOSEOUT: PR-OPS-002
# Portfolio RAG — Fix GCS Restore on Startup (PR-011)
# v2.1.0 → v2.1.1
# Date: 2026-03-06

---

## Sprint Summary

Fixed a race condition where Cloud Run's TCP startup probe passed before the ASGI lifespan (GCS restore + ChromaDB init) completed. Requests routed to the uninitialized worker saw empty collections. Fix: added a `_ready` health gate and switched to an HTTP startup probe on `/health`.

## Root Cause

| Factor | Detail |
|--------|--------|
| Startup probe type | TCP on port 8080 — passes when gunicorn master binds, before worker is ready |
| ASGI lifespan | GCS restore runs during lifespan startup (before `yield`) |
| Race window | ~30-60s between gunicorn bind and lifespan completion |
| Symptom | /beekes returns "No results found" (etymology collection empty) |

## Changes

### app/main.py
- Added `_ready = False` module-level flag
- Set `_ready = True` at end of lifespan startup (after GCS restore + ChromaDB init)
- `/health` returns 503 with "Starting up — GCS restore in progress" until `_ready=True`
- Added `HTTPException` import

### app/core/vectorstore.py
- `restore_from_gcs()`: Added `exc_info=True` to error log for full tracebacks

### app/core/config.py
- VERSION: 2.1.0 → 2.1.1

### Cloud Run service config
- Startup probe: TCP → HTTP (`httpGet.path=/health, httpGet.port=8080`)
- `periodSeconds=10, timeoutSeconds=5, failureThreshold=24` (240s max startup)

## Verification

1. Fresh deploy (revision 00041-4c4): both collections restored from GCS ✅
2. Health: `{"status":"healthy","version":"2.1.1","collections":{"portfolio":545,"etymology":1835}}` ✅
3. Semantic query `etymology of cosmos` → κόσμος (page 804, score 0.4706) ✅
4. No manual ingest performed before verification ✅

## Acceptance Criteria

- [x] Phase 0 forensic report delivered (6-item diagnosis)
- [x] Root cause identified: TCP startup probe race condition
- [x] After fresh deploy (no manual ingest): semantic query returns κόσμος
- [x] Health returns 503 during startup, 200 after
- [x] Startup probe is HTTP on /health (verified via gcloud describe)

## Deploy Info

- Revision: portfolio-rag-00041-4c4
- Service URL: https://portfolio-rag-57478301787.us-central1.run.app
- Health: `{"status":"healthy","version":"2.1.1","collections":{"portfolio":545,"etymology":1835}}`

## Gotchas for Next Session

1. **Startup probe is HTTP now**: If `/health` logic changes, ensure it still returns 200 after startup. 503 during startup is intentional.
2. **Git Bash path mangling**: `/health` gets converted to `C:/Program Files/Git/health` in gcloud commands. Use `//health` or `gcloud.cmd` to avoid this.
3. **cc-deploy can't read logs**: `gcloud logging read` fails with PERMISSION_DENIED for cc-deploy SA.
4. **Memory budget**: 1Gi memory shared between app, tmpfs (/tmp), and ChromaDB data. GCS backup is ~39 MiB compressed.
