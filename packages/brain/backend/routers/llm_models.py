"""API selezione e probe modelli LLM."""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/api/llm/models")
async def llm_models():
    from backend.core.ollama_model_router import get_probe_status, list_ollama_models
    models = await list_ollama_models()
    probe = await get_probe_status()
    return {"models": models, "probe": probe}


@router.post("/api/llm/probe")
async def llm_probe_models(force: bool = Query(default=True)):
    from backend.core.ollama_model_router import probe_all_models
    return await probe_all_models(force=force)


@router.get("/api/llm/select")
async def llm_select_model(q: str = "", tier: str | None = None):
    from backend.core.ollama_model_router import classify_task, get_probe_status, select_model
    if tier in ("fast", "balanced", "capable"):
        probe = await get_probe_status()
        model = (probe.get("by_tier") or {}).get(tier) or probe.get("recommended")
        return {"tier": tier, "model": model, "probe": probe}
    model, meta = await select_model(q)
    return {"model": model, **meta}
