# SESSION CLOSEOUT: PR-011
# Portfolio RAG — Code Collection (Source Code Semantic Search)
# v2.1.1 → v2.2.0
# Date: 2026-03-07

---

## Sprint Summary

Added a third ChromaDB collection `code` that indexes Python/SQL/JS source files from 6 GitHub repos. Semantic search can now find actual implementation code, not just documentation. Extended `/semantic` with `repo` and `filetype` filter params.

## Changes

### app/core/config.py
- VERSION: 2.1.1 → 2.2.0

### app/core/vectorstore.py
- `query()` + `_query_collection()`: Added `where: dict` parameter for metadata filtering
- `collection_counts()`: Added "code" to tracked collections

### app/api/ingest.py
- Added `CODE_REPOS`, `CODE_EXTENSIONS`, `CODE_EXCLUDE`, `MAX_FILE_CHARS` constants
- Added `_classify_filetype()` and `_get_commit_date()` helpers
- Added `POST /ingest/code` endpoint (placed before `/ingest/{repo_name}` catch-all)
  - Shallow clones 6 repos, walks .py/.sql/.js files, classifies, embeds, upserts
  - Prepends metadata header to each doc for richer embedding context
  - Backs up to GCS after completion
  - Idempotent by doc_id (`{repo}::{filepath}`)

### app/api/query.py
- `/semantic` now accepts `repo` and `filetype` query params
- "code" added to VALID_COLLECTIONS
- Code results include `repo`, `filepath`, `filetype`, `last_commit` fields
- ChromaDB `where` clause built from filters and passed to vectorstore

### Dockerfile
- Added `git` to apt-get install (required for `git clone` in /ingest/code)

## Repos Indexed

| Repo | Files |
|------|-------|
| etymython | 178 |
| super-flashcards | 141 |
| metapm | 80 |
| artforge | 70 |
| harmonylab | 35 |
| portfolio-rag | 17 |
| **Total** | **521** |

Note: `pie-network-graph` not on GitHub under coreyprator — skipped.

## Acceptance Tests

| Test | Query | Result |
|------|-------|--------|
| 1 | ArtForge story persistence save voice_id | app/routers/stories.py [route] score=0.4524 ✅ |
| 2 | MetaPM roadmap_requirements schema columns | scripts/backlog_schema.sql [schema] score=0.5213 ✅ |
| 3 | Cross-repo ChromaDB semantic search endpoint | portfolio-rag/app/core/vectorstore.py score=0.4392 ✅ |

## Phase 2: GCS Backup

GCS backup post-ingest contains 5 collection UUIDs (was 3 before) — code collection is included.
Backup: gs://portfolio-rag-backups-57478301787/chromadb-backup/chroma_persist.tar.gz

## Deploy Info

- Revision: portfolio-rag-00044-7cn
- Health: `{"status":"healthy","version":"2.2.0","collections":{"portfolio":552,"etymology":1835,"code":521}}`

## Gotchas for Next Session

1. **pie-network-graph not on GitHub**: No `coreyprator/pie-network-graph` repo — the PIE Network Graph app is not in GitHub (may be private or under a different name).
2. **Code ingestion is not automated**: `/ingest/code` must be triggered manually. Cloud Scheduler only runs `/ingest/portfolio` daily. Add a scheduler job if automated re-indexing needed.
3. **Max file chars**: Files truncated at 24,000 chars (~6,000 tokens) to stay under OpenAI embedding limit. Large generated files (like index.html) are truncated.
4. **Filetype classification uses regex-like string matching in Python** — not actual regex. The `classify_filetype` function uses `in` checks on lowercased paths.
