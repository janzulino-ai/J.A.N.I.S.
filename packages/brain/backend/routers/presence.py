"""API presenza — claim, migrate, stato."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from backend.core import presence

router = APIRouter()
logger = logging.getLogger("JANIS.Presence")

TOUR_STEPS = [
    ("desktop", "widget", "Ciao. Sono JANIS. Ora sono sul tuo PC Windows."),
    ("mac-mini", "window", "Mi sposto sul Mac Mini."),
    ("ipad-pro-2020", "mobile", "Adesso sono sul tuo iPad Pro."),
    ("iphone-15-pro-max", "mobile", "Sono sul tuo iPhone 15 Pro Max."),
    ("iphone-14-pro", "mobile", "Oppure sul tuo iPhone 14 Pro."),
]


class ClaimBody(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    surface: str = Field(default="widget")
    session_id: str = Field(default="")
    follow_user: bool = True


class MigrateBody(BaseModel):
    surface: str
    device_id: str | None = None


@router.get("/api/presence")
async def get_presence():
    return presence.get_presence()


@router.post("/api/presence/claim")
async def post_claim(body: ClaimBody):
    return await presence.claim(
        body.device_id,
        body.surface,  # type: ignore[arg-type]
        session_id=body.session_id,
        follow_user=body.follow_user,
    )


@router.post("/api/presence/migrate")
async def post_migrate(body: MigrateBody):
    return await presence.migrate(body.surface, body.device_id)  # type: ignore[arg-type]


async def _run_presence_tour():
    from backend.routers.websocket import manager

    for device_id, surface, speak_text in TOUR_STEPS:
        state = await presence.claim(device_id, surface, follow_user=True)  # type: ignore[arg-type]
        await manager.broadcast({
            "type": "presence_changed",
            "device_id": device_id,
            "surface": surface,
            "speak_text": speak_text,
            "power_state": state.get("power_state"),
            "tour": True,
        })
        logger.info("Tour presenza: %s — %s", device_id, speak_text)
        await asyncio.sleep(9)


@router.post("/api/presence/tour")
async def post_presence_tour(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_presence_tour)
    return {"ok": True, "steps": [{"device_id": d, "text": t} for d, _, t in TOUR_STEPS]}
