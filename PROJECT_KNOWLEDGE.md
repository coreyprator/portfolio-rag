# Portfolio RAG -- Project Knowledge Document
Generated: 2026-02-28 by CC Session
Updated: 2026-02-28 -- Sprint "PR-MS1" (v0.1.0)
Purpose: Canonical reference for all AI sessions working on this project.

### Latest Session Update -- 2026-02-28 (PR-MS1 Portfolio RAG MVP, v0.1.0)

- **MVP Sprint**: Document retrieval service for CC sessions
- **Current Version**: v0.1.0 -- **DEPLOYED** to Cloud Run
- **Service URL**: https://portfolio-rag-57478301787.us-central1.run.app
- **Health**: `{"status":"healthy","version":"0.1.0","documents":73,"repos_indexed":6}`
- **Features**:
  - Ingests canonical .md files from all 6 portfolio repos via GitHub REST API
  - In-memory document index with keyword search
  - Auto-ingests on startup (all repos)
  - GitHub webhook handler for push-triggered re-ingestion
  - Checkpoint extraction from `<!-- CHECKPOINT: xxx -->` comments
  - Prompt delivery (POST/GET /prompts) for CAI-to-CC workflow
  - Artifact delivery (POST/GET /artifacts/{sprint_id}) for closeout data
- **Endpoints**:
  - `GET /health` -- version, doc count, repos indexed, last ingest time
  - `GET /latest/{doc_type}?repo=` -- bootstrap, pk, intent, culture, claude, closeout
  - `GET /document/{repo}/{path}` -- full content + metadata
  - `GET /query?q=&repo=` -- keyword search with scored results + snippets
  - `GET /checkpoints` -- all checkpoint codes across repos
  - `POST /ingest/{repo}` -- re-ingest specific repo
  - `POST /ingest/all` -- re-ingest all repos
  - `POST /webhook/github` -- GitHub push webhook with HMAC validation
  - `POST /prompts`, `GET /prompts/{id}` -- prompt delivery
  - `POST /artifacts/{sprint_id}`, `GET /artifacts/{sprint_id}` -- artifact delivery

## Architecture

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11, FastAPI, gunicorn + uvicorn |
| Deployment | Google Cloud Run (service: portfolio-rag) |
| GCP Project | super-flashcards-475210 |
| Region | us-central1 |
| Document Source | GitHub REST API (6 repos) |
| Index | In-memory Python dict (keyword search) |
| Auth | GitHub PAT for API access (env var GITHUB_TOKEN) |
| CI/CD | GitHub Actions -> gcloud run deploy |

## Repos Indexed

| Repo | Owner | Canonical Docs Found |
|------|-------|---------------------|
| project-methodology | coreyprator | PK, CULTURE, Bootstrap, CLAUDE, closeouts |
| metapm | coreyprator | PK, INTENT, CLAUDE, closeouts |
| ArtForge | coreyprator | PK, INTENT, CLAUDE |
| harmonylab | coreyprator | PK, INTENT, CLAUDE |
| Super-Flashcards | coreyprator | PK, INTENT, CLAUDE |
| etymython | coreyprator | PK, INTENT, CLAUDE |

## Future Roadmap

| Sprint | Scope |
|--------|-------|
| PR-MS2 | ChromaDB + OpenAI embeddings, semantic search, Cloud Storage persistence |
| PR-MS3 | Beekes PDF digitization, UI dashboard, cross-document linking |

## Deployment

```bash
# Direct deploy
gcloud run deploy portfolio-rag --source . --region us-central1 --allow-unauthenticated --project super-flashcards-475210

# Set GitHub token
gcloud run services update portfolio-rag --region us-central1 --set-env-vars "GITHUB_TOKEN=ghp_xxx"

# Trigger re-ingestion
curl -X POST https://portfolio-rag-57478301787.us-central1.run.app/ingest/all
```
