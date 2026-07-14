"""API dashboard HUD kiosk."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.core.hud_dashboard import build_dashboard

router = APIRouter()


@router.get("/api/hud/dashboard")
async def hud_dashboard(refresh_inventory: bool = Query(default=False)):
    return await build_dashboard(refresh_inventory=refresh_inventory)
