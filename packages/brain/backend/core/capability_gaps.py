"""Registro gap di capacità — loop auto-miglioramento JANIS."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAPS_FILE = Path(__file__).resolve().parent / "capability_gaps.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not GAPS_FILE.exists():
        return {"gaps": [], "updated_at": None}
    try:
        with open(GAPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("gaps", [])
        return data
    except Exception:
        return {"gaps": [], "updated_at": None}


def _save(data: dict) -> None:
    data["updated_at"] = _now()
    GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GAPS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log_gap(
    description: str,
    *,
    context: str | None = None,
    tool: str | None = None,
    severity: str = "medium",
    proposed_fix: str | None = None,
) -> dict:
    """Registra un nuovo gap di capacità."""
    data = _load()
    entry = {
        "id": str(uuid.uuid4()),
        "description": description.strip(),
        "context": (context or "").strip() or None,
        "tool": tool,
        "severity": severity,
        "proposed_fix": proposed_fix,
        "status": "open",
        "created_at": _now(),
        "resolved_at": None,
    }
    data["gaps"].append(entry)
    # Mantieni ultimi 200 gap
    data["gaps"] = data["gaps"][-200:]
    _save(data)
    return entry


def list_gaps(status: str | None = None) -> list[dict]:
    gaps = _load().get("gaps", [])
    if status:
        gaps = [g for g in gaps if g.get("status") == status]
    return list(reversed(gaps))


def resolve_gap(gap_id: str, resolution: str | None = None) -> dict | None:
    data = _load()
    for gap in data["gaps"]:
        if gap.get("id") == gap_id:
            gap["status"] = "resolved"
            gap["resolved_at"] = _now()
            if resolution:
                gap["resolution"] = resolution
            _save(data)
            return gap
    return None


def get_gap(gap_id: str) -> dict | None:
    for gap in _load().get("gaps", []):
        if gap.get("id") == gap_id:
            return gap
    return None


def stats() -> dict[str, Any]:
    gaps = _load().get("gaps", [])
    open_gaps = [g for g in gaps if g.get("status") == "open"]
    return {
        "total": len(gaps),
        "open": len(open_gaps),
        "resolved": len(gaps) - len(open_gaps),
        "updated_at": _load().get("updated_at"),
    }
