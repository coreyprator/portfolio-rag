"""Admin endpoints: scheduled re-ingestion trigger."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.core.config import settings
from app.core.vectorstore import backup_to_gcs
from app.services.ingestion import ingest_portfolio, ingest_jazz_theory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

REINGESTABLE = {"portfolio", "jazz_theory"}


async def _reingest_collection(collection: str):
    """Run re-ingestion for a named collection and back up to GCS."""
    try:
        if collection == "portfolio":
            result = await ingest_portfolio()
        elif collection == "jazz_theory":
            result = await ingest_jazz_theory()
        else:
            logger.error(f"Unknown collection for reingest: {collection}")
            return
        chunks = result.get("chunks", 0)
        logger.info(f"Re-ingestion complete: {collection} — {chunks} chunks")
        backup_to_gcs()
    except Exception as e:
        logger.error(f"Re-ingestion failed for {collection}: {e}")


@router.post("/reingest")
async def trigger_reingest(
    background_tasks: BackgroundTasks,
    collection: str = "portfolio",
    x_reingest_token: str | None = Header(None),
):
    """Trigger background re-ingestion of a collection.

    Protected by X-Reingest-Token header.
    Supports: portfolio, jazz_theory.
    """
    expected = settings.REINGEST_TOKEN
    if not expected:
        raise HTTPException(500, "REINGEST_TOKEN not configured")
    if x_reingest_token != expected:
        raise HTTPException(403, "Forbidden")
    if collection not in REINGESTABLE:
        raise HTTPException(400, f"collection must be one of: {', '.join(sorted(REINGESTABLE))}")

    background_tasks.add_task(_reingest_collection, collection)
    return {"status": "ingestion_started", "collection": collection}
