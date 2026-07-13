"""API pagine IDE: progetti, impostazioni, memoria, setup."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.brain import check_ollama
from backend.core.llm_router import active_provider_label, get_active_provider
from backend.core.runtime_config import CURSOR_REASONING_MODELS, REASONING_PROVIDERS, get_runtime
from backend.core.tools.memory_tool import (
    export_memories,
    get_memory_by_id,
    list_memories,
    search_memories,
)

router = APIRouter()
logger = logging.getLogger("JANIS.Pages")


class SettingsUpdate(BaseModel):
    ollama_model: str | None = None
    llm_provider: str | None = None
    openrouter_model: str | None = None
    cursor_api_key: str | None = None
    cursor_model: str | None = None
    tts_voice: str | None = None
    tts_rate: str | None = None
    tts_pitch: str | None = None
    janis_workspace: str | None = None
    janis_movies_path: str | None = None
    janis_scan_roots: str | None = None


def _env_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".env"


def _update_env(updates: dict[str, str]) -> None:
    path = _env_path()
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    keys = set(updates.keys())
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    _apply_settings_env(updates)


def _apply_settings_env(updates: dict[str, str]) -> None:
    field_map = {
        "OLLAMA_MODEL": "OLLAMA_MODEL",
        "LLM_PROVIDER": "LLM_PROVIDER",
        "OPENROUTER_MODEL": "OPENROUTER_MODEL",
        "CURSOR_API_KEY": "CURSOR_API_KEY",
        "CURSOR_MODEL": "CURSOR_MODEL",
        "JANIS_TTS_VOICE": "JANIS_TTS_VOICE",
        "JANIS_TTS_RATE": "JANIS_TTS_RATE",
        "JANIS_TTS_PITCH": "JANIS_TTS_PITCH",
        "JANIS_WORKSPACE": "JANIS_WORKSPACE",
        "JANIS_MOVIES_PATH": "JANIS_MOVIES_PATH",
        "JANIS_SCAN_ROOTS": "JANIS_SCAN_ROOTS",
    }
    for k, v in updates.items():
        os.environ[k] = v
        attr = field_map.get(k, k)
        if hasattr(settings, attr):
            object.__setattr__(settings, attr, v)


async def _broadcast_enrichment(result: dict) -> None:
    from backend.core.tools.memory_tool import get_knowledge_stats
    from backend.routers.websocket import manager

    for node in result.get("nodes") or []:
        await manager.broadcast({"type": "brain_node", "node": node})
    if result.get("nodes_created"):
        await manager.broadcast({"type": "knowledge_grow", "amount": result["nodes_created"]})
    await manager.broadcast({"type": "knowledge_update", **get_knowledge_stats()})


async def _enrich_folders_task() -> None:
    from backend.core.folder_knowledge import enrich_all_folders

    try:
        result = await enrich_all_folders()
        await _broadcast_enrichment(result)
        logger.info("Arricchimento cartelle completato: %s neuroni", result.get("nodes_created", 0))
    except Exception:
        logger.exception("Arricchimento cartelle fallito")


@router.get("/api/projects")
async def list_projects():
    root = Path(settings.JANIS_PROJECT_DIR).resolve()
    parent = root.parent
    items: list[dict] = []
    if parent.exists():
        for child in sorted(parent.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                items.append({
                    "name": child.name,
                    "path": str(child),
                    "is_current": child.resolve() == root,
                })
    return {"root": str(parent), "current": str(root), "projects": items}


@router.get("/api/settings")
async def get_settings():
    ollama = await check_ollama()
    rt = get_runtime()
    llm = await get_active_provider()
    key = settings.CURSOR_API_KEY
    from backend.core.folder_knowledge import get_knowledge_status

    knowledge = get_knowledge_status()
    return {
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_online": ollama.get("online", False),
        "ollama_models": ollama.get("models", []),
        "llm_provider": settings.LLM_PROVIDER,
        "llm_active": llm.get("active", active_provider_label()),
        "llm_detail": llm,
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "openrouter_model": settings.OPENROUTER_MODEL,
        "cursor_configured": bool(key),
        "cursor_api_key_hint": (key[:6] + "…" + key[-4:]) if len(key) > 12 else ("•••" if key else ""),
        "cursor_model": settings.CURSOR_MODEL,
        "cursor_models": list(CURSOR_REASONING_MODELS),
        "reasoning_providers": list(REASONING_PROVIDERS),
        "paid_mode": rt.paid_mode,
        "reasoning_provider": rt.reasoning_provider,
        "cursor_reasoning_model": rt.cursor_reasoning_model,
        "cursor_code_enabled": rt.cursor_code_enabled,
        "openrouter_when_paid": rt.openrouter_when_paid,
        "tts_voice": settings.JANIS_TTS_VOICE,
        "tts_rate": settings.JANIS_TTS_RATE,
        "tts_pitch": settings.JANIS_TTS_PITCH,
        "janis_workspace": settings.JANIS_WORKSPACE,
        "janis_project_dir": settings.JANIS_PROJECT_DIR,
        "janis_movies_path": settings.JANIS_MOVIES_PATH,
        "janis_scan_roots": settings.JANIS_SCAN_ROOTS,
        "knowledge": knowledge,
        "port": settings.PORT,
    }


@router.get("/api/knowledge/status")
async def knowledge_status():
    from backend.core.folder_knowledge import get_knowledge_status

    return get_knowledge_status()


@router.post("/api/knowledge/enrich")
async def knowledge_enrich(background_tasks: BackgroundTasks):
    background_tasks.add_task(_enrich_folders_task)
    return {"ok": True, "status": "started"}


@router.post("/api/settings")
async def save_settings(body: SettingsUpdate, background_tasks: BackgroundTasks):
    mapping = {
        "OLLAMA_MODEL": body.ollama_model,
        "LLM_PROVIDER": body.llm_provider,
        "OPENROUTER_MODEL": body.openrouter_model,
        "CURSOR_API_KEY": body.cursor_api_key,
        "CURSOR_MODEL": body.cursor_model,
        "JANIS_TTS_VOICE": body.tts_voice,
        "JANIS_TTS_RATE": body.tts_rate,
        "JANIS_TTS_PITCH": body.tts_pitch,
        "JANIS_WORKSPACE": body.janis_workspace,
        "JANIS_MOVIES_PATH": body.janis_movies_path,
        "JANIS_SCAN_ROOTS": body.janis_scan_roots,
    }
    updates = {k: v for k, v in mapping.items() if v is not None}
    if updates.get("CURSOR_API_KEY") is not None and not str(updates["CURSOR_API_KEY"]).strip():
        updates.pop("CURSOR_API_KEY", None)
    trigger_enrich = bool(updates.get("JANIS_SCAN_ROOTS", "").strip())
    if updates:
        _update_env(updates)
    if trigger_enrich and "JANIS_SCAN_ROOTS" in updates:
        background_tasks.add_task(_enrich_folders_task)
    return await get_settings()


@router.get("/api/fs/drives")
async def fs_drives():
    from backend.core.fs_browser import list_drives

    return {"drives": list_drives()}


@router.get("/api/fs/browse")
async def fs_browse(path: str = Query(default="")):
    from backend.core.fs_browser import browse_directory

    try:
        return browse_directory(path or None)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/setup/status")
async def setup_status():
    ollama = await check_ollama()
    env_exists = _env_path().exists()
    return {
        "env_exists": env_exists,
        "ollama_online": ollama.get("online", False),
        "ollama_models": ollama.get("models", []),
        "model_configured": bool(settings.OLLAMA_MODEL),
        "ready": env_exists and ollama.get("online", False),
    }


@router.get("/api/memory")
async def memory_list(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str = Query(""),
):
    if q.strip():
        items = search_memories(q.strip())
        return {"items": items, "total": len(items), "page": 1, "pages": 1}
    return list_memories(page=page, limit=limit)


@router.get("/api/memory/search")
async def memory_search(q: str = Query(..., min_length=1)):
    return {"items": search_memories(q)}


@router.get("/api/memory/export")
async def memory_export():
    data = export_memories()
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="janis-memory-export.json"'},
    )


@router.get("/api/memory/brain-status")
async def memory_brain_status():
    """Risposta deterministica memoria — non passa dall'LLM."""
    from backend.core.tools.memory_tool import memory_status, _load, count_memories_by_tags

    text = await memory_status({})
    return {
        "ok": True,
        "text": text,
        "total": len(_load()),
        "mac": count_memories_by_tags(["knowledge-mac"]),
        "brain_version": 5,
    }


@router.get("/api/memory/{memory_id}")
async def memory_detail(memory_id: str):
    entry = get_memory_by_id(memory_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Memoria non trovata")
    return entry
