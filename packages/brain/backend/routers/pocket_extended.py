"""API Pocket v3.1 — telemetry, vision, push."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.device_auth import require_device_token

router = APIRouter(dependencies=[Depends(require_device_token)])
logger = logging.getLogger("JANIS.Pocket")


class TelemetryBody(BaseModel):
    device_id: str
    timestamp: str = ""
    battery: dict | None = None
    location: dict | None = None
    environment: dict | None = None
    network: dict | None = None
    health: dict | None = None
    owner: dict | None = None
    body: dict | None = None
    capabilities: list[str] = Field(default_factory=list)


class VisionBody(BaseModel):
    device_id: str
    image_base64: str
    timestamp: str = ""
    owner: dict | None = None
    context: str = ""


class PushRegisterBody(BaseModel):
    device_id: str
    token: str
    platform: str = "ios"
    owner: dict | None = None


def _telemetry_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "telemetry"
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.post("/api/pocket/telemetry")
async def pocket_telemetry(body: TelemetryBody):
    ts = body.timestamp or datetime.now(timezone.utc).isoformat()
    payload = body.model_dump()
    payload["received_at"] = datetime.now(timezone.utc).isoformat()
    fname = f"{body.device_id}_{ts.replace(':', '-')}.json"
    (_telemetry_dir() / fname).write_text(json.dumps(payload), encoding="utf-8")
    from backend.core import presence
    await presence.claim(body.device_id, "mobile")
    return {"ok": True}


@router.post("/api/pocket/vision")
async def pocket_vision(body: VisionBody):
    vision_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "vision"
    vision_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "device_id": body.device_id,
        "timestamp": body.timestamp or datetime.now(timezone.utc).isoformat(),
        "context": body.context,
        "owner": body.owner,
        "bytes": len(body.image_base64),
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (vision_dir / f"{body.device_id}_{ts}.json").write_text(json.dumps(meta), encoding="utf-8")
    return {"ok": True, "stored": True}


@router.post("/api/pocket/push/register")
async def pocket_push_register(body: PushRegisterBody):
    reg_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "push"
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / f"{body.device_id}.json").write_text(
        json.dumps(body.model_dump()),
        encoding="utf-8",
    )
    return {"ok": True, "registered": body.device_id}
