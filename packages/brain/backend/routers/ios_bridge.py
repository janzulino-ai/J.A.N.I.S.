"""Bridge comandi iOS — pending/complete."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.device_auth import require_device_token

router = APIRouter(dependencies=[Depends(require_device_token)])


def _bridge_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "bridge"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pending_path(device: str) -> Path:
    return _bridge_dir() / f"{device}_pending.json"


def _completed_path(device: str) -> Path:
    return _bridge_dir() / f"{device}_completed.jsonl"


class CompleteBody(BaseModel):
    device: str
    command_id: str
    result: dict = Field(default_factory=dict)


def enqueue_command(device: str, action: str, params: dict | None = None) -> str:
    cmd_id = str(uuid.uuid4())[:8]
    pending = []
    path = _pending_path(device)
    if path.exists():
        pending = json.loads(path.read_text(encoding="utf-8"))
    pending.append({"id": cmd_id, "action": action, "params": params or {}})
    path.write_text(json.dumps(pending), encoding="utf-8")
    return cmd_id


@router.get("/api/devices/ios/pending")
async def ios_pending(device: str = Query(...)):
    path = _pending_path(device)
    if not path.exists():
        return {"commands": []}
    commands = json.loads(path.read_text(encoding="utf-8"))
    return {"commands": commands}


@router.post("/api/devices/ios/complete")
async def ios_complete(body: CompleteBody):
    path = _pending_path(body.device)
    if path.exists():
        pending = json.loads(path.read_text(encoding="utf-8"))
        pending = [c for c in pending if c.get("id") != body.command_id]
        path.write_text(json.dumps(pending), encoding="utf-8")
    line = json.dumps({
        "command_id": body.command_id,
        "device": body.device,
        "result": body.result,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    with (_completed_path(body.device)).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return {"ok": True}
