"""Artifact delivery endpoints. Store and retrieve closeout artifacts by sprint."""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


@dataclass
class ArtifactRecord:
    id: str
    sprint_id: str
    content: str
    artifact_type: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: str = ""


# In-memory store: sprint_id -> list of artifacts
_artifacts: dict[str, list[ArtifactRecord]] = {}


class ArtifactCreate(BaseModel):
    content: str
    artifact_type: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/artifacts/{sprint_id}")
async def create_artifact(sprint_id: str, body: ArtifactCreate):
    """Store a closeout artifact for a sprint."""
    artifact_id = uuid.uuid4().hex[:8].upper()
    record = ArtifactRecord(
        id=artifact_id,
        sprint_id=sprint_id,
        content=body.content,
        artifact_type=body.artifact_type,
        metadata=body.metadata,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    if sprint_id not in _artifacts:
        _artifacts[sprint_id] = []
    _artifacts[sprint_id].append(record)
    return {"id": artifact_id, "sprint_id": sprint_id, "created_at": record.created_at}


@router.get("/artifacts/{sprint_id}")
async def get_artifacts(sprint_id: str):
    """Retrieve all artifacts for a sprint."""
    records = _artifacts.get(sprint_id, [])
    return {
        "sprint_id": sprint_id,
        "artifacts": [asdict(r) for r in records],
        "total": len(records),
    }
