"""API Capability Fabric."""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(tags=["capabilities"])


@router.get("/api/capabilities")
async def api_capabilities(wave: int = Query(default=1, ge=1, le=9)):
    from backend.core.capabilities import build_fabric

    return await build_fabric(wave=wave)
