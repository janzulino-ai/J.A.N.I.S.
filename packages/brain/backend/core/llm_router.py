"""Router LLM multi-provider: Ollama → Cursor (PRO) → OpenRouter."""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from backend.config import settings
from backend.core.runtime_config import effective_reasoning_provider, get_runtime

logger = logging.getLogger("JANIS.LLMRouter")


async def _ollama_chat(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.62, "num_ctx": 8192},
            },
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


async def _openrouter_chat(messages: list[dict]) -> str:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY non configurata")
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8001",
                "X-Title": "JANIS",
            },
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": messages,
                "temperature": 0.62,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


async def _cursor_chat(messages: list[dict]) -> str:
    from backend.core.cursor_llm import cursor_chat

    rt = get_runtime()
    model = rt.cursor_reasoning_model or settings.CURSOR_MODEL
    return await cursor_chat(messages, model)


def _build_chain(provider: str) -> list[str]:
    rt = get_runtime()
    p = (provider or "ollama").lower().strip()

    if not rt.paid_mode:
        if p == "openrouter":
            return ["openrouter", "ollama"]
        if p == "auto":
            return ["ollama", "openrouter"] if settings.OPENROUTER_API_KEY else ["ollama"]
        return ["ollama", "openrouter"] if settings.OPENROUTER_API_KEY else ["ollama"]

    if p == "cursor":
        chain = ["cursor"]
        if rt.openrouter_when_paid and settings.OPENROUTER_API_KEY:
            chain.append("openrouter")
        chain.append("ollama")
        return chain
    if p == "openrouter":
        return ["openrouter", "cursor", "ollama"] if settings.CURSOR_API_KEY else ["openrouter", "ollama"]
    if p == "auto":
        chain = []
        if settings.CURSOR_API_KEY:
            chain.append("cursor")
        chain.append("ollama")
        if settings.OPENROUTER_API_KEY:
            chain.append("openrouter")
        return chain or ["ollama"]
    return ["ollama", "openrouter"] if settings.OPENROUTER_API_KEY else ["ollama"]


async def chat(messages: list[dict]) -> tuple[str, str]:
    """Invia messaggi al provider attivo con catena di fallback."""
    provider = effective_reasoning_provider()
    chain = _build_chain(provider)

    last_err: Exception | None = None
    for p in chain:
        try:
            if p == "cursor":
                if not settings.CURSOR_API_KEY:
                    raise RuntimeError("CURSOR_API_KEY mancante")
                return await _cursor_chat(messages), "cursor"
            if p == "ollama":
                return await _ollama_chat(messages), "ollama"
            if p == "openrouter":
                return await _openrouter_chat(messages), "openrouter"
        except Exception as e:
            last_err = e
            logger.warning("Provider %s fallito: %s", p, e)
            continue

    raise RuntimeError(f"Tutti i provider LLM falliti: {last_err}")


async def chat_stream(messages: list[dict]) -> AsyncIterator[str]:
    """Stream da Ollama (Cursor/OpenRouter non streamati in v1)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.62, "num_ctx": 8192},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def get_active_provider() -> dict:
    """Stato provider attivo per UI."""
    rt = get_runtime()
    configured = effective_reasoning_provider()
    ollama_ok = False
    openrouter_ok = bool(settings.OPENROUTER_API_KEY)
    cursor_ok = bool(settings.CURSOR_API_KEY)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    chain = _build_chain(configured)
    active = "none"
    for p in chain:
        if p == "ollama" and ollama_ok:
            active = "ollama"
            break
        if p == "cursor" and cursor_ok:
            active = "cursor"
            break
        if p == "openrouter" and openrouter_ok:
            active = "openrouter"
            break

    return {
        "configured": configured,
        "active": active,
        "paid_mode": rt.paid_mode,
        "reasoning_provider": rt.reasoning_provider if rt.paid_mode else configured,
        "cursor_reasoning_model": rt.cursor_reasoning_model,
        "ollama_online": ollama_ok,
        "openrouter_configured": openrouter_ok,
        "cursor_configured": cursor_ok,
        "ollama_model": settings.OLLAMA_MODEL,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "cursor_model": settings.CURSOR_MODEL,
        "fallback_chain": chain,
    }


def active_provider_label() -> str:
    provider = effective_reasoning_provider()
    if provider == "cursor" and settings.CURSOR_API_KEY:
        return "cursor"
    if provider == "openrouter" and settings.OPENROUTER_API_KEY:
        return "openrouter"
    return "ollama"
