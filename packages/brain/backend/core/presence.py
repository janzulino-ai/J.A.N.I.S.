"""Presence Service — dove vive JANIS (anchor) e conversazione collegata."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from backend.config import settings

logger = logging.getLogger("JANIS.Presence")

Surface = Literal["wallpaper", "terminal", "widget", "mobile", "headless", "window", "fullscreen"]
PowerState = Literal["full", "terminal", "dormant", "headless"]

_STATE_FILE = Path(settings.JANIS_PROJECT_DIR) / "data" / "presence" / "state.json"

_default = {
    "device_id": "desktop",
    "surface": "widget",
    "session_id": "",
    "follow_user": True,
    "power_state": "full",
    "updated_at": "",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    _ensure_dir()
    if not _STATE_FILE.exists():
        s = {**_default, "updated_at": _now()}
        save_state(s)
        return s
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        return {**_default, **data}
    except Exception:
        return {**_default, "updated_at": _now()}


def save_state(state: dict) -> dict:
    _ensure_dir()
    state["updated_at"] = _now()
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def get_presence() -> dict:
    return load_state()


def _apply_power(surface: str, device_id: str) -> str:
    from backend.core.desktop_state import set_mode
    from backend.core.desktop_power import set_monitor_power

    if surface == "mobile" or device_id.startswith("pocket"):
        set_mode("overlay")
        set_monitor_power(True)
        return "dormant"
    if surface == "headless":
        set_mode("hidden")
        set_monitor_power(False)
        return "headless"
    if surface == "wallpaper":
        set_mode("wallpaper")
        set_monitor_power(True)
        return "full"
    if surface == "terminal":
        set_mode("overlay")
        set_monitor_power(True)
        return "terminal"
    set_mode("overlay" if surface == "widget" else "browser")
    set_monitor_power(True)
    return "full"


async def claim(
    device_id: str,
    surface: Surface,
    *,
    session_id: str = "",
    follow_user: bool = True,
) -> dict:
    """Sposta presenza su device/superficie. Conversazione segue session_id."""
    prev = load_state()
    state = {
        **prev,
        "device_id": device_id.strip().lower(),
        "surface": surface,
        "follow_user": follow_user,
        "session_id": session_id or prev.get("session_id") or "",
    }
    state["power_state"] = _apply_power(surface, device_id)
    save_state(state)
    logger.info("Presence claim: %s @ %s (was %s@%s)", device_id, surface, prev.get("device_id"), prev.get("surface"))

    try:
        from backend.routers.websocket import manager

        manager.set_active(state["device_id"])
        await manager.broadcast({
            "type": "presence_changed",
            "device_id": state["device_id"],
            "surface": state["surface"],
            "power_state": state.get("power_state"),
            "follow_user": state.get("follow_user", True),
        })
    except Exception:
        pass

    return state


async def migrate(surface: Surface, device_id: str | None = None) -> dict:
    cur = load_state()
    return await claim(
        device_id or cur.get("device_id", "desktop"),
        surface,
        session_id=cur.get("session_id", ""),
        follow_user=cur.get("follow_user", True),
    )


def active_device_id() -> str:
    return load_state().get("device_id", "desktop")


def should_route_io_to(device_id: str) -> bool:
    """I/O (TTS/STT reply) solo sull'anchor attivo se follow_user."""
    st = load_state()
    if not st.get("follow_user", True):
        return True
    active = st.get("device_id", "desktop")
    return device_id.lower() == active.lower()
