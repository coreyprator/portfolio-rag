"""Prompt delivery endpoints. Store and retrieve CC prompts by link."""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


@dataclass
class PromptRecord:
    id: str
    content: str
    title: Optional[str] = None
    sprint_id: Optional[str] = None
    created_at: str = ""


# In-memory store
_prompts: dict[str, PromptRecord] = {}


class PromptCreate(BaseModel):
    content: str
    title: Optional[str] = None
    sprint_id: Optional[str] = None


@router.post("/prompts")
async def create_prompt(body: PromptCreate):
    """Store a CC prompt and return a retrieval link."""
    prompt_id = uuid.uuid4().hex[:8].upper()
    record = PromptRecord(
        id=prompt_id,
        content=body.content,
        title=body.title,
        sprint_id=body.sprint_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _prompts[prompt_id] = record
    return {"id": prompt_id, "url": f"/prompts/{prompt_id}", "created_at": record.created_at}


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Retrieve a CC prompt by ID."""
    record = _prompts.get(prompt_id.upper())
    if not record:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
    return asdict(record)


@router.get("/prompts")
async def list_prompts():
    """List all stored prompts (metadata only, no content)."""
    items = [
        {"id": r.id, "title": r.title, "sprint_id": r.sprint_id, "created_at": r.created_at}
        for r in sorted(_prompts.values(), key=lambda r: r.created_at, reverse=True)
    ]
    return {"prompts": items, "total": len(items)}
