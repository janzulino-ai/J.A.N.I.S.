"""Percezione — STT, visione, modelli locali."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Perception")

_VISION_MODEL_HINTS = ("llava", "moondream", "bakllava", "minicpm-v", "vision")


async def list_vision_models() -> list[str]:
    from backend.core.ollama_model_router import list_ollama_models

    models = await list_ollama_models()
    return [m for m in models if any(h in m.lower() for h in _VISION_MODEL_HINTS)]


async def build_perception_status() -> dict:
    from backend.routers.stt import _probe_engines, SUPPORTED_FORMATS
    from backend.core import win_vm

    stt = _probe_engines()
    vision_models = await list_vision_models()
    vm = await win_vm.vm_status()
    pocket_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "vision"
    recent_vision = sorted(pocket_dir.glob("*.json"), reverse=True)[:5] if pocket_dir.exists() else []

    return {
        "local_first": settings.LOCAL_FIRST,
        "cloud_llm_allowed": settings.CLOUD_LLM_ALLOWED,
        "stt": {
            **stt,
            "formats": list(SUPPORTED_FORMATS),
            "endpoint": "/api/stt",
            "diagnostic": "/api/stt/diagnostic",
        },
        "vision": {
            "pocket_endpoint": "/api/pocket/vision",
            "ollama_vision_models": vision_models,
            "vision_ready": bool(vision_models),
            "recent_frames": len(recent_vision),
            "last_frame": recent_vision[0].name if recent_vision else None,
            "note": (
                "Invia frame da Pocket iOS o usa describe_vision."
                if not vision_models
                else f"Modelli vision locali: {', '.join(vision_models)}"
            ),
        },
        "win_vm": {
            "state": vm.get("state"),
            "available": vm.get("available"),
            "tool": "win_vm action=start",
        },
        "hardware_needed": [
            item for item, ok in [
                ("microfono (Pocket o client web)", stt.get("ready")),
                ("camera (Pocket app)", bool(recent_vision)),
                ("modello vision Ollama (llava/moondream)", bool(vision_models)),
            ] if not ok
        ],
    }


async def describe_image(
    *,
    device_id: str | None = None,
    path: str | None = None,
    image_base64: str | None = None,
    context: str = "",
) -> str:
    # W6i: prova vision-mcp prima (OCR/video agentic)
    if path or image_base64:
        try:
            from backend.core.sidecar_call import call_mcp, pick_mcp_tool
            from backend.core.mcp_client import get_session

            tools = await (await get_session("vision")).list_tools()
            name = pick_mcp_tool(tools, "describe", "analyze", "ocr", "vision", "describe_image")
            if name:
                out = await call_mcp(
                    "vision",
                    name,
                    {
                        "path": path or "",
                        "image_base64": image_base64 or "",
                        "prompt": context or "Descrivi in italiano",
                    },
                )
                if out and not out.startswith("MCP error"):
                    return out
        except Exception:
            logger.debug("vision-mcp skip", exc_info=True)

    vision_models = await list_vision_models()
    if not vision_models:
        return (
            "Visione locale non disponibile: nessun modello Ollama vision installato.\n"
            "Sul server: ollama pull llava:7b (o moondream)\n"
            "Oppure invia frame da Pocket → POST /api/pocket/vision\n"
            "Sidecar: vision-mcp in servers.json"
        )

    b64 = image_base64
    if not b64 and path:
        p = Path(path)
        if p.is_file():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    if not b64 and device_id:
        pocket_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "vision"
        matches = sorted(pocket_dir.glob(f"{device_id}_*.json"), reverse=True)
        if matches:
            meta = json.loads(matches[0].read_text(encoding="utf-8"))
            return (
                f"Ultimo frame Pocket {matches[0].name}: {meta.get('bytes', 0)} bytes "
                f"(immagine non persistita — serve image_base64 da Pocket).\n"
                f"Contesto: {meta.get('context') or '—'}"
            )
        return f"Nessun frame Pocket per device {device_id}"

    if not b64:
        pocket_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "vision"
        matches = sorted(pocket_dir.glob("*.json"), reverse=True)
        if matches:
            meta = json.loads(matches[0].read_text(encoding="utf-8"))
            return (
                f"Frame recente {matches[0].name} — solo metadati ({meta.get('bytes')} bytes).\n"
                "Per descrizione LLM serve image_base64 nel body Pocket vision."
            )
        return "Nessuna immagine: invia da Pocket o passa image_base64/path."

    model = vision_models[0]
    prompt = context or "Descrivi l'immagine in italiano, breve."
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                    "stream": False,
                },
            )
            r.raise_for_status()
            text = r.json().get("message", {}).get("content", "")
            return text.strip() or "Modello vision ha risposto vuoto."
    except Exception as e:
        logger.warning("Vision describe failed: %s", e)
        return f"Errore visione locale ({model}): {e}"
