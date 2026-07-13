"""API runtime — modalità PRO e provider ragionamento rapido."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.llm_router import get_active_provider
from backend.core.runtime_config import (
    CURSOR_REASONING_MODELS,
    REASONING_PROVIDERS,
    RuntimeConfig,
    get_runtime,
    save_runtime,
)

router = APIRouter()


class RuntimeUpdate(BaseModel):
    paid_mode: bool | None = None
    reasoning_provider: str | None = Field(default=None, pattern="^(ollama|cursor|openrouter|auto)$")
    cursor_reasoning_model: str | None = None
    cursor_code_enabled: bool | None = None
    openrouter_when_paid: bool | None = None


@router.get("/api/runtime")
async def get_runtime_state():
    rt = get_runtime()
    provider = await get_active_provider()
    return {
        **rt.to_dict(),
        "cursor_api_configured": bool(settings.CURSOR_API_KEY),
        "cursor_code_model": settings.CURSOR_MODEL,
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "ollama_model": settings.OLLAMA_MODEL,
        "effective_reasoning": provider.get("active"),
        "reasoning_providers": list(REASONING_PROVIDERS),
        "cursor_models": list(CURSOR_REASONING_MODELS),
        "llm_configured": provider,
    }


@router.post("/api/runtime")
async def update_runtime(body: RuntimeUpdate):
    rt = get_runtime()
    data = rt.to_dict()
    for key in ("paid_mode", "reasoning_provider", "cursor_reasoning_model", "cursor_code_enabled", "openrouter_when_paid"):
        val = getattr(body, key, None)
        if val is not None:
            data[key] = val
    saved = save_runtime(RuntimeConfig(**data))
    provider = await get_active_provider()
    return {
        **saved.to_dict(),
        "cursor_api_configured": bool(settings.CURSOR_API_KEY),
        "effective_reasoning": provider.get("active"),
        "llm_configured": provider,
    }


@router.post("/api/runtime/toggle-paid")
async def toggle_paid_mode():
    rt = get_runtime()
    saved = save_runtime(RuntimeConfig(**{**rt.to_dict(), "paid_mode": not rt.paid_mode}))
    provider = await get_active_provider()
    return {
        **saved.to_dict(),
        "effective_reasoning": provider.get("active"),
    }
