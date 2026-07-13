"""Ragionamento JANIS via Cursor SDK (API a pagamento)."""
from __future__ import annotations

import asyncio
import logging

from backend.config import settings

logger = logging.getLogger("JANIS.CursorLLM")


def _messages_to_prompt(messages: list[dict]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(f"[Sistema]\n{content}")
        elif role == "assistant":
            parts.append(f"[JANIS]\n{content}")
        else:
            parts.append(f"[Utente]\n{content}")
    text = "\n\n".join(parts).strip()
    if len(text) > 120_000:
        text = text[-120_000:]
    return text


def _cursor_chat_sync(messages: list[dict], model: str) -> str:
    from backend.core.cursor_win_patch import apply_cursor_sdk_patches, reset_cursor_bridge

    apply_cursor_sdk_patches()
    reset_cursor_bridge()
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

    if not settings.CURSOR_API_KEY:
        raise RuntimeError("CURSOR_API_KEY non configurata")

    prompt = _messages_to_prompt(messages)
    if not prompt:
        raise RuntimeError("Prompt vuoto")

    cwd = settings.JANIS_PROJECT_DIR
    logger.info("Cursor reasoning model=%s cwd=%s", model, cwd)

    result = Agent.prompt(
        prompt,
        AgentOptions(
            api_key=settings.CURSOR_API_KEY,
            model=model,
            local=LocalAgentOptions(cwd=cwd),
        ),
    )
    output = getattr(result, "result", None) or str(result)
    status = getattr(result, "status", "unknown")
    logger.info("Cursor reasoning status=%s len=%d", status, len(output or ""))
    return (output or "").strip()


async def cursor_chat(messages: list[dict], model: str | None = None) -> str:
    m = model or settings.CURSOR_MODEL
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _cursor_chat_sync, messages, m)
