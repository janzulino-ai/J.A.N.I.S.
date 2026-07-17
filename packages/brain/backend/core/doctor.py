"""JANIS doctor — health check + self-heal leggero (W7b).

Onestà: MCP in PATH / servers.json senza integrazione E2E ≠ successo.
Lo stato capacità prodotto viene dalla Capability Fabric.
"""
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

    # Sidecar process (presence only — optional)
    comfy = (getattr(settings, "COMFYUI_URL", None) or "http://127.0.0.1:8188").rstrip("/")
    comfy_ok = await _http_ok(f"{comfy}/system_stats")
    checks.append({"id": "comfyui", "ok": comfy_ok, "detail": comfy, "optional": True})

    searx = (getattr(settings, "SEARXNG_URL", None) or "http://127.0.0.1:8080").rstrip("/")
    searx_ok = await _http_ok(f"{searx}/")
    checks.append({"id": "searxng", "ok": searx_ok, "detail": searx, "optional": True})

    # MCP: session_active = integrato; command_found da solo ≠ ok
    mcp_status: list[dict] = []
    try:
        from backend.core.mcp_client import mcp_server_status

        mcp_status = await mcp_server_status()
        for s in mcp_status:
            integrated = bool(s.get("session_active"))
            found = bool(s.get("command_found"))
            checks.append(
                {
                    "id": f"mcp:{s.get('name')}",
                    "ok": integrated,
                    "detail": (
                        "session attiva"
                        if integrated
                        else (
                            f"binario presente ma NON integrato (session off): {s.get('command')}"
                            if found
                            else f"assente: {s.get('command')}"
                        )
                    ),
                    "optional": True,
                    "session": integrated,
                    "command_found": found,
                    "integrated": integrated,
                }
            )
    except Exception as e:
        checks.append({"id": "mcp", "ok": False, "detail": str(e), "optional": True})

    # Capability Fabric (fonte di verità prodotto)
    fabric: dict[str, Any] = {}
    try:
        from backend.core.capabilities import build_fabric

        fabric = await build_fabric(wave=1)
        for cap in fabric.get("capabilities") or []:
            status = cap.get("status") or "red"
            e2e = bool(cap.get("e2e"))
            checks.append(
                {
                    "id": f"cap:{cap.get('id')}",
                    "ok": e2e and status == "green",
                    "optional": True,
                    "detail": f"{status} · {cap.get('backend')} · {cap.get('detail')}",
                    "e2e": e2e,
                    "status": status,
                }
            )
        checks.append(
            {
                "id": "capability_fabric",
                "ok": fabric.get("summary") != "red",
                "detail": (
                    f"summary={fabric.get('summary')} "
                    f"green={fabric.get('counts', {}).get('green')} "
                    f"e2e={fabric.get('counts', {}).get('e2e')}"
                ),
            }
        )
    except Exception as e:
        checks.append({"id": "capability_fabric", "ok": False, "detail": str(e)})

    # Fleet
    try:
        from backend.core.fleet.manager import fleet_manager

        fleet = fleet_manager.fleet_status()
        online = sum(1 for n in (fleet.get("nodes") or []) if n.get("online") or n.get("status") == "online")
        checks.append({"id": "fleet", "ok": True, "detail": f"nodes_online={online}", "fleet": fleet})
    except Exception as e:
        checks.append({"id": "fleet", "ok": False, "detail": str(e)})

    # CLI presence — solo informativo (non conta come fail/success integrazione)
    for cmd in ("codebase-memory-mcp", "officecli", "agent-reach", "reach", "mobile-mcp", "rg"):
        which = shutil.which(cmd)
        checks.append(
            {
                "id": f"cli:{cmd}",
                "ok": True,
                "optional": True,
                "informational": True,
                "present": bool(which),
                "detail": (
                    f"presente PATH={which} (presenza ≠ E2E; vedi cap:*)"
                    if which
                    else "missing (ok se fallback nativo / fabric green)"
                ),
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

    # Summary: Ollama required; fabric = verità capacità prodotto
    fabric_summary = fabric.get("summary") if fabric else None
    fab_it = {"green": "verde", "amber": "giallo", "red": "rosso"}.get(
        fabric_summary or "", fabric_summary
    )
    if required_fail:
        summary = "rosso"
    elif fab_it in ("verde", "giallo", "rosso"):
        summary = fab_it
    else:
        summary = "giallo" if optional_fail else "verde"

    return {
        "ok": len(required_fail) == 0,
        "heal": heal,
        "actions": actions,
        "required_fail": [c["id"] for c in required_fail],
        "optional_fail": [c["id"] for c in optional_fail],
        "checks": checks,
        "mcp": mcp_status,
        "fabric": {
            "summary": fabric.get("summary"),
            "counts": fabric.get("counts"),
            "capabilities": fabric.get("capabilities"),
        }
        if fabric
        else None,
        "summary": summary,
    }
