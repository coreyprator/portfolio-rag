"""Prompt delivery endpoints with lifecycle tracking."""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

VALID_STATUSES = {"draft", "sent", "in_progress", "completed", "needs_fixes", "completed_with_fixes"}


@dataclass
class PromptRecord:
    id: str
    content: str
    title: Optional[str] = None
    sprint_id: Optional[str] = None
    project: Optional[str] = None
    status: str = "draft"
    created_at: str = ""
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None
    handoff_id: Optional[str] = None
    uat_id: Optional[str] = None
    version_before: Optional[str] = None
    version_after: Optional[str] = None
    notes: Optional[str] = None


# In-memory store
_prompts: dict[str, PromptRecord] = {}


class PromptCreate(BaseModel):
    content: str
    title: Optional[str] = None
    sprint_id: Optional[str] = None
    project: Optional[str] = None
    status: str = "draft"
    version_before: Optional[str] = None
    notes: Optional[str] = None


class PromptUpdate(BaseModel):
    status: Optional[str] = None
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None
    handoff_id: Optional[str] = None
    uat_id: Optional[str] = None
    version_after: Optional[str] = None
    notes: Optional[str] = None


@router.post("/prompts")
async def create_prompt(body: PromptCreate):
    """Store a CC prompt and return a retrieval link."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}. Valid: {sorted(VALID_STATUSES)}")
    prompt_id = uuid.uuid4().hex[:8].upper()
    record = PromptRecord(
        id=prompt_id,
        content=body.content,
        title=body.title,
        sprint_id=body.sprint_id,
        project=body.project,
        status=body.status,
        created_at=datetime.now(timezone.utc).isoformat(),
        version_before=body.version_before,
        notes=body.notes,
    )
    _prompts[prompt_id] = record
    return {"id": prompt_id, "url": f"/prompts/{prompt_id}", "created_at": record.created_at}


# /prompts/active must be defined BEFORE /prompts/{prompt_id}
@router.get("/prompts/active")
async def get_active_prompts():
    """Get prompts with status 'sent' or 'in_progress'."""
    active = [
        asdict(r) for r in sorted(_prompts.values(), key=lambda r: r.created_at, reverse=True)
        if r.status in ("sent", "in_progress")
    ]
    return {"prompts": active, "total": len(active)}


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Retrieve a CC prompt by ID."""
    record = _prompts.get(prompt_id.upper())
    if not record:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
    return asdict(record)


@router.patch("/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, body: PromptUpdate):
    """Update prompt status and lifecycle fields."""
    record = _prompts.get(prompt_id.upper())
    if not record:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}. Valid: {sorted(VALID_STATUSES)}")
        record.status = body.status
    if body.sent_at is not None:
        record.sent_at = body.sent_at
    if body.completed_at is not None:
        record.completed_at = body.completed_at
    if body.handoff_id is not None:
        record.handoff_id = body.handoff_id
    if body.uat_id is not None:
        record.uat_id = body.uat_id
    if body.version_after is not None:
        record.version_after = body.version_after
    if body.notes is not None:
        record.notes = body.notes

    return asdict(record)


@router.get("/prompts")
async def list_prompts(project: Optional[str] = None, status: Optional[str] = None, sort: str = "created_at"):
    """List all stored prompts (metadata only, no content). Filterable by project and status."""
    items = []
    for r in _prompts.values():
        if project and r.project != project:
            continue
        if status and r.status != status:
            continue
        items.append({
            "id": r.id,
            "title": r.title,
            "sprint_id": r.sprint_id,
            "project": r.project,
            "status": r.status,
            "created_at": r.created_at,
            "sent_at": r.sent_at,
            "completed_at": r.completed_at,
            "handoff_id": r.handoff_id,
            "uat_id": r.uat_id,
        })
    items.sort(key=lambda x: x.get(sort, x["created_at"]) or "", reverse=True)
    return {"prompts": items, "total": len(items)}
