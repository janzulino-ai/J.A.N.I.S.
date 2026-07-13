"""API emergenza SOS da Pocket."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.device_auth import require_device_token
from backend.routers.ios_bridge import enqueue_command

router = APIRouter(dependencies=[Depends(require_device_token)])
logger = logging.getLogger("JANIS.Emergency")


class SOSBody(BaseModel):
    device_id: str
    text: str = ""
    location: dict | None = None
    environment: dict | None = None
    health: dict | None = None
    identity: dict | None = None
    image_base64: str = ""
    timestamp: str = ""


@router.post("/api/emergency/sos")
async def emergency_sos(body: SOSBody):
    sos_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "emergency"
    sos_dir.mkdir(parents=True, exist_ok=True)
    payload = body.model_dump()
    payload["received_at"] = datetime.now(timezone.utc).isoformat()
    payload.pop("image_base64", None)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (sos_dir / f"sos_{body.device_id}_{ts}.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    if body.image_base64:
        from backend.routers.pocket_extended import VisionBody
        from backend.routers import pocket_extended as pe

        await pe.pocket_vision(
            VisionBody(
                device_id=body.device_id,
                image_base64=body.image_base64,
                context="emergency.sos",
                owner=body.identity,
            )
        )
    enqueue_command(body.device_id, "notify", {
        "title": "JANIS SOS",
        "body": body.text or "Richiesta di aiuto",
    })
    logger.warning("SOS da %s: %s", body.device_id, body.text[:120] if body.text else "(no text)")
    return {
        "ok": True,
        "urgency": "high",
        "logged": True,
        "message": "Emergenza registrata sul brain Linux. Fleet e client notificati.",
    }
