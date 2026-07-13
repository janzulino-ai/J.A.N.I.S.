"""API Pocket — ingest note e sync."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.device_auth import require_device_token
from backend.core.tools.registry import execute_tool

router = APIRouter(dependencies=[Depends(require_device_token)])


class PocketIngestBody(BaseModel):
    text: str = Field(min_length=1)
    title: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    claim_presence: bool = True


@router.post("/api/pocket/ingest")
async def pocket_ingest(body: PocketIngestBody):
    if body.claim_presence:
        from backend.core import presence

        await presence.claim("pocket", "mobile")

    tags = list(body.tags) + ["pocket", "voice-note"]
    result = await execute_tool(
        "remember",
        {"text": body.text, "tags": tags, "source": "pocket"},
    )
    return {
        "ok": True,
        "remember": result[:500],
        "title": body.title or body.text[:80],
    }
