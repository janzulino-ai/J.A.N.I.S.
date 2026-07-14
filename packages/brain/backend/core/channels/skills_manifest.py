"""Manifest skill canali — pattern OpenClaw."""
from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings

DEFAULT_SKILLS = [
    {
        "id": "telegram",
        "channel": "telegram",
        "enabled": True,
        "capabilities": ["inbound", "outbound", "groups_mention"],
    },
    {
        "id": "whatsapp",
        "channel": "whatsapp",
        "enabled": True,
        "capabilities": ["inbound", "outbound"],
        "requires": ["WHATSAPP_BRIDGE_URL"],
    },
    {
        "id": "pocket",
        "channel": "pocket",
        "enabled": True,
        "capabilities": ["stt", "ingest", "presence"],
    },
]


def skills_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "channels" / "skills.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_channel_skills() -> list[dict]:
    path = skills_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(DEFAULT_SKILLS, indent=2), encoding="utf-8")
    return list(DEFAULT_SKILLS)


def channel_skill_status() -> dict:
    skills = load_channel_skills()
    out = []
    for s in skills:
        reqs = s.get("requires") or []
        ok = all(bool(getattr(settings, r, "") or "") for r in reqs) if reqs else True
        if s.get("channel") == "telegram":
            ok = ok and bool(settings.TELEGRAM_BOT_TOKEN)
        out.append({**s, "ready": ok})
    return {"skills": out, "ready_count": sum(1 for x in out if x.get("ready"))}
