"""Portfolio RAG - Document Retrieval Service for CC Sessions"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.index import document_index
from app.api import query, ingest, webhook, prompts, artifacts
from app.services.github import GitHubClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Portfolio RAG",
    description="Document retrieval service for CC sessions. Indexes all text files from portfolio repos.",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

logger.info("=" * 60)
logger.info(f"Portfolio RAG v{settings.VERSION} STARTING UP")
logger.info("=" * 60)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        errors.append(f"{field}: {error.get('msg', 'unknown error')}")
    detail = "; ".join(errors)
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled: {request.method} {request.url}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
    )


# Health check
@app.get("/health")
@app.head("/health")
async def health_check():
    stats = document_index.stats()
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "build": settings.BUILD,
        "documents": stats["document_count"],
        "repos_indexed": len(stats["repos_indexed"]),
        "doc_types": stats["doc_types"],
        "last_ingest": stats["last_ingest"],
    }


@app.get("/")
async def root():
    return {
        "service": "Portfolio RAG",
        "version": settings.VERSION,
        "docs": "/docs",
        "endpoints": [
            "GET /health",
            "GET /documents?repo=&doc_type=&has_checkpoint=&extension=&path_contains=",
            "GET /latest/all",
            "GET /latest/{doc_type}?repo=",
            "GET /document/{repo}/{path}",
            "GET /query?q=&repo=",
            "GET /checkpoints",
            "POST /ingest/all",
            "POST /ingest/{repo}",
            "POST /webhook/github",
            "POST /prompts",
            "GET /prompts/{id}",
            "GET /prompts/active",
            "PATCH /prompts/{id}",
            "GET /prompts?project=&status=",
            "POST /artifacts/{sprint_id}",
            "GET /artifacts/{sprint_id}",
        ],
    }


# Startup: ingest all repos
@app.on_event("startup")
async def startup_ingest():
    if not settings.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set. Skipping startup ingestion. Use POST /ingest/all to trigger manually.")
        return
    logger.info(f"Starting initial ingestion of {len(settings.REPOS)} repos...")
    client = GitHubClient(token=settings.GITHUB_TOKEN, owner=settings.REPO_OWNER)
    total = 0
    for repo in settings.REPOS:
        try:
            docs = await client.fetch_repo_docs(repo)
            for doc in docs:
                document_index.add(doc)
            total += len(docs)
            logger.info(f"Ingested {repo}: {len(docs)} documents")
        except Exception as e:
            logger.warning(f"Failed to ingest {repo} on startup: {e}")
    logger.info(f"Startup ingestion complete: {total} documents from {len(settings.REPOS)} repos")


# Include routers
app.include_router(query.router, tags=["Query"])
app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(webhook.router, tags=["Webhook"])
app.include_router(prompts.router, tags=["Prompts"])
app.include_router(artifacts.router, tags=["Artifacts"])
