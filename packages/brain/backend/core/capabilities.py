"""Capability Fabric — stato E2E delle capacità prodotto (Wave 1).

Verde solo se un percorso end-to-end funziona (sidecar integrato O fallback nativo JANIS).
MCP presente in PATH / servers.json senza sessione attiva ≠ ready.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Capabilities")

Status = Literal["green", "amber", "red"]


@dataclass(frozen=True)
class CapDef:
    id: str
    label: str
    category: str  # sense | create | act | core
    ownership: str  # janis | sidecar | hybrid
    tools: tuple[str, ...]
    description: str


WAVE1: tuple[CapDef, ...] = (
    CapDef(
        "chat",
        "Chat / LLM",
        "core",
        "janis",
        ("chat",),
        "Conversazione locale via Ollama (cervello JANIS).",
    ),
    CapDef(
        "code_search",
        "Code search",
        "create",
        "hybrid",
        ("code_search", "code_symbol", "code_context"),
        "Grafo DeusData se disponibile; altrimenti ripgrep/pathlib nativo.",
    ),
    CapDef(
        "doc_read",
        "Documenti",
        "sense",
        "hybrid",
        ("doc_read",),
        "Docling MCP se attivo; fallback testo/PDF nativo.",
    ),
    CapDef(
        "vision",
        "Visione",
        "sense",
        "hybrid",
        ("describe_vision",),
        "vision-mcp se attivo; altrimenti Ollama vision (llava/moondream).",
    ),
    CapDef(
        "research",
        "Ricerca locale",
        "sense",
        "janis",
        ("research",),
        "Pipeline JANIS: SearXNG + fetch + sintesi Ollama (no signup API).",
    ),
    CapDef(
        "image_gen",
        "Generazione immagini",
        "create",
        "hybrid",
        ("image_gen",),
        "ComfyUI sidecar + serving JANIS /api/media.",
    ),
    CapDef(
        "media_api",
        "Media API",
        "create",
        "janis",
        (),
        "Serving file generati su /api/media/images.",
    ),
    CapDef(
        "voice",
        "Voce (STT/TTS)",
        "core",
        "janis",
        ("perception_status",),
        "Microfono → /api/stt → chat; risposte via /api/tts.",
    ),
)


async def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code < 500
    except Exception:
        return False


async def _mcp_session_active(name: str) -> bool:
    try:
        from backend.core.mcp_client import mcp_enabled, mcp_server_status

        if not mcp_enabled():
            return False
        for s in await mcp_server_status():
            if s.get("name") == name and s.get("session_active"):
                return True
    except Exception:
        logger.debug("mcp status fail for %s", name, exc_info=True)
    return False


async def _ollama_online() -> bool:
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    return await _http_ok(f"{base}/api/tags")


async def _has_vision_model() -> bool:
    try:
        from backend.core.perception import list_vision_models

        return bool(await list_vision_models())
    except Exception:
        return False


def _rg_available() -> bool:
    return bool(shutil.which("rg") or shutil.which("ripgrep"))


def _native_code_ready() -> bool:
    """Fallback nativo sempre disponibile (pathlib; rg opzionale)."""
    root = Path(settings.JANIS_WORKSPACE or settings.JANIS_PROJECT_DIR or ".")
    try:
        return root.exists()
    except OSError:
        return False


def _media_dir_ready() -> bool:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "images"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p.is_dir()
    except OSError:
        return False


async def _comfy_online() -> bool:
    comfy = (getattr(settings, "COMFYUI_URL", None) or "http://127.0.0.1:8188").rstrip("/")
    return await _http_ok(f"{comfy}/system_stats")


async def _searx_online() -> bool:
    from backend.core.local_research import searx_base

    return await _http_ok(f"{searx_base()}/")


async def probe_capability(cap: CapDef) -> dict[str, Any]:
    """Probe E2E: green solo se un percorso utilizzabile esiste."""
    backend = "none"
    detail = ""
    status: Status = "red"
    e2e = False

    if cap.id == "chat":
        ok = await _ollama_online()
        backend = "ollama" if ok else "none"
        status = "green" if ok else "red"
        e2e = ok
        detail = settings.OLLAMA_BASE_URL if ok else "Ollama offline"

    elif cap.id == "code_search":
        mcp_ok = await _mcp_session_active("codebase-memory")
        native = _native_code_ready()
        if mcp_ok:
            backend, status, e2e = "deusdata-mcp", "green", True
            detail = "MCP codebase-memory attivo"
        elif native:
            backend = "native-rg" if _rg_available() else "native-pathlib"
            status, e2e = "green", True
            detail = f"Fallback nativo ({backend})"
        else:
            detail = "Workspace assente e DeusData non connesso"

    elif cap.id == "doc_read":
        mcp_ok = await _mcp_session_active("docling")
        if mcp_ok:
            backend, status, e2e = "docling-mcp", "green", True
            detail = "Docling MCP attivo"
        else:
            backend, status, e2e = "native-text-pdf", "green", True
            detail = "Fallback nativo testo/PDF (senza Docling)"

    elif cap.id == "vision":
        mcp_ok = await _mcp_session_active("vision")
        ollama_v = await _has_vision_model()
        if mcp_ok:
            backend, status, e2e = "vision-mcp", "green", True
            detail = "vision-mcp attivo"
        elif ollama_v:
            backend, status, e2e = "ollama-vision", "green", True
            detail = "Ollama vision model presente"
        else:
            status = "red"
            detail = "Nessun modello vision Ollama né vision-mcp"

    elif cap.id == "research":
        searx = await _searx_online()
        oll = await _ollama_online()
        if searx and oll:
            backend, status, e2e = "local_research", "green", True
            detail = "SearXNG + Ollama (pipeline JANIS)"
        elif searx or oll:
            backend, status, e2e = "local_research", "amber", False
            detail = f"Parziale: searx={searx} ollama={oll}"
        else:
            detail = "SearXNG e Ollama offline — research non E2E"

    elif cap.id == "image_gen":
        comfy = await _comfy_online()
        media = _media_dir_ready()
        if comfy and media:
            backend, status, e2e = "comfyui+/api/media", "green", True
            detail = "ComfyUI online + media dir"
        elif comfy:
            backend, status, e2e = "comfyui", "amber", False
            detail = "ComfyUI online ma media dir non pronta"
        else:
            detail = f"ComfyUI offline ({getattr(settings, 'COMFYUI_URL', '8188')})"

    elif cap.id == "media_api":
        ok = _media_dir_ready()
        backend = "janis-/api/media"
        status = "green" if ok else "red"
        e2e = ok
        detail = "/api/media/images" if ok else "media dir non creabile"

    elif cap.id == "voice":
        stt_ready = False
        try:
            from backend.routers.stt import _probe_engines

            stt_ready = bool(_probe_engines().get("ready"))
        except Exception:
            pass
        oll = await _ollama_online()
        if stt_ready and oll:
            backend, status, e2e = "stt+tts+chat", "green", True
            detail = "STT ready + Ollama (pipeline voce→tool)"
        elif stt_ready:
            backend, status, e2e = "stt", "amber", False
            detail = "STT ok ma Ollama offline — chat voce degradato"
        else:
            detail = "faster-whisper non pronto (pip install + STT_ENABLED)"

    return {
        "id": cap.id,
        "label": cap.label,
        "category": cap.category,
        "ownership": cap.ownership,
        "tools": list(cap.tools),
        "description": cap.description,
        "status": status,
        "e2e": e2e,
        "backend": backend,
        "detail": detail,
        "wave": 1,
    }


async def build_fabric(*, wave: int | None = 1) -> dict[str, Any]:
    caps = [await probe_capability(c) for c in WAVE1]
    if wave is not None:
        caps = [c for c in caps if c.get("wave") == wave]
    green = sum(1 for c in caps if c["status"] == "green")
    amber = sum(1 for c in caps if c["status"] == "amber")
    red = sum(1 for c in caps if c["status"] == "red")
    e2e_ok = sum(1 for c in caps if c.get("e2e"))
    summary: Status = "green"
    if red:
        summary = "amber" if green else "red"
    elif amber:
        summary = "amber"
    return {
        "ok": True,
        "wave": wave or 1,
        "mode": "A",  # WSL brain + Windows app (Mode B = Linux system)
        "summary": summary,
        "counts": {"green": green, "amber": amber, "red": red, "e2e": e2e_ok, "total": len(caps)},
        "capabilities": caps,
        "principle": "Verde solo se percorso E2E (sidecar integrato o fallback nativo JANIS).",
        "sidecar_vs_owned": {
            "sidecar_process": ["Ollama", "ComfyUI", "SearXNG", "MCP stdio opzionali"],
            "janis_owned": [
                "Capability Fabric",
                "local_research",
                "native code_search/doc_read",
                "/api/media",
                "ReAct tools",
                "HUD/Agent UX",
            ],
        },
    }
