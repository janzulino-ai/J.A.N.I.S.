"""JANIS doctor — health check + self-heal leggero (W7b)."""
from __future__ import annotations

import logging
import shutil
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Doctor")


async def _http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code < 500
    except Exception:
        return False


async def run_doctor(*, heal: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    actions: list[str] = []

    # Ollama
    ollama_url = settings.OLLAMA_BASE_URL.rstrip("/")
    ollama_ok = await _http_ok(f"{ollama_url}/api/tags")
    if not ollama_ok and heal:
        try:
            from backend.core.ollama_service import ensure_ollama_running

            ollama_ok = await ensure_ollama_running()
            actions.append("ollama_ensure")
        except Exception as e:
            actions.append(f"ollama_ensure_fail:{e}")
    checks.append({"id": "ollama", "ok": ollama_ok, "detail": ollama_url})

    # ComfyUI
    comfy = (getattr(settings, "COMFYUI_URL", None) or "http://127.0.0.1:8188").rstrip("/")
    comfy_ok = await _http_ok(f"{comfy}/system_stats")
    checks.append({"id": "comfyui", "ok": comfy_ok, "detail": comfy, "optional": True})

    # SearXNG
    searx = (getattr(settings, "SEARXNG_URL", None) or "http://127.0.0.1:8080").rstrip("/")
    searx_ok = await _http_ok(f"{searx}/")
    checks.append({"id": "searxng", "ok": searx_ok, "detail": searx, "optional": True})

    # MCP servers
    mcp_status: list[dict] = []
    try:
        from backend.core.mcp_client import mcp_server_status

        mcp_status = await mcp_server_status()
        for s in mcp_status:
            checks.append(
                {
                    "id": f"mcp:{s.get('name')}",
                    "ok": bool(s.get("command_found")),
                    "detail": s.get("command"),
                    "optional": s.get("name") not in ("codebase-memory",),
                    "session": s.get("session_active"),
                }
            )
    except Exception as e:
        checks.append({"id": "mcp", "ok": False, "detail": str(e)})

    # Fleet
    try:
        from backend.core.fleet.manager import fleet_manager

        fleet = fleet_manager.fleet_status()
        online = sum(1 for n in (fleet.get("nodes") or []) if n.get("online") or n.get("status") == "online")
        checks.append({"id": "fleet", "ok": True, "detail": f"nodes_online={online}", "fleet": fleet})
    except Exception as e:
        checks.append({"id": "fleet", "ok": False, "detail": str(e)})

    # CLI tools
    for cmd in ("codebase-memory-mcp", "officecli", "agent-reach", "reach", "mobile-mcp"):
        checks.append(
            {
                "id": f"cli:{cmd}",
                "ok": bool(shutil.which(cmd)),
                "optional": True,
                "detail": shutil.which(cmd) or "missing",
            }
        )

    # Board / autonomy
    try:
        from backend.core.orchestrator.board import board_status

        board = board_status()
        checks.append(
            {
                "id": "orchestrator",
                "ok": True,
                "detail": f"autonomy={board.get('autonomy_level')} tickets={board.get('tickets')}",
            }
        )
    except Exception as e:
        checks.append({"id": "orchestrator", "ok": False, "detail": str(e)})

    required_fail = [c for c in checks if not c.get("ok") and not c.get("optional")]
    optional_fail = [c for c in checks if not c.get("ok") and c.get("optional")]

    return {
        "ok": len(required_fail) == 0,
        "heal": heal,
        "actions": actions,
        "required_fail": [c["id"] for c in required_fail],
        "optional_fail": [c["id"] for c in optional_fail],
        "checks": checks,
        "mcp": mcp_status,
        "summary": (
            "verde"
            if not required_fail and len(optional_fail) < 3
            else ("giallo" if not required_fail else "rosso")
        ),
    }
