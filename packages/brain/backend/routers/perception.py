"""API percezione — STT, visione, sensori."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/perception/status")
async def perception_status_api():
    from backend.core.perception import build_perception_status

    return {"ok": True, **await build_perception_status()}
