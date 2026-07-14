"""API Cursor — agent streaming per app desktop Windows."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shlex
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import settings

from backend.core.security import wsl_path_to_windows

router = APIRouter()
logger = logging.getLogger("JANIS.CursorBridge")


class CursorAgentRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    cwd: str | None = None


class CursorChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


def _windows_repo() -> Path:
    monorepo = getattr(settings, "JANIS_MONOREPO_ROOT", "") or ""
    if monorepo:
        win = wsl_path_to_windows(monorepo)
        if win:
            return Path(win)
    win = wsl_path_to_windows(str(Path(settings.JANIS_PROJECT_DIR).resolve().parent.parent))
    if win:
        return Path(win)
    win = Path(r"C:\APP IA\JANIS")
    if win.exists():
        return win
    return Path(settings.JANIS_PROJECT_DIR).resolve().parents[2]


def _wsl_to_win_path(path: str) -> str:
    return wsl_path_to_windows(path) or path


@router.get("/api/cursor/status")
async def cursor_status():
    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    key_ok = bool(settings.CURSOR_API_KEY and settings.CURSOR_API_KEY.strip())
    return {
        "ok": True,
        "cursor_api_configured": key_ok,
        "cursor_model": settings.CURSOR_MODEL,
        "paid_mode": rt.paid_mode,
        "cursor_code_enabled": rt.cursor_code_enabled,
        "reasoning_provider": rt.reasoning_provider,
        "platform": platform.system(),
        "windows_delegate": platform.system() == "Linux",
        "ready": key_ok and rt.paid_mode and rt.cursor_code_enabled,
        "project_dir": settings.JANIS_PROJECT_DIR,
        "windows_project": wsl_path_to_windows(settings.JANIS_PROJECT_DIR)
        or settings.JANIS_PROJECT_DIR,
    }


async def _stream_cursor_events(prompt: str, cwd: str | None):
    """Yield SSE events from cursor_code (in-process or Windows delegate)."""
    if platform.system() == "Linux" and Path("/mnt/c/Windows").exists():
        win_repo = _windows_repo()
        ps1 = win_repo / "infra" / "windows" / "run-cursor-agent.ps1"
        win_cwd = _wsl_to_win_path(cwd or settings.JANIS_PROJECT_DIR)
        ps = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        if not ps1.exists():
            yield _sse({"type": "error", "message": f"Script mancante: {ps1}"})
            return
        cmd = (
            f'& "{ps1}" -Prompt {shlex.quote(prompt)} '
            f'-Cwd {shlex.quote(win_cwd)}'
        )
        proc = await asyncio.create_subprocess_exec(
            ps,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                yield _sse(json.loads(text))
            except json.JSONDecodeError:
                yield _sse({"type": "cursor_stream", "chunk": text + "\n", "done": False})
        await proc.wait()
        return

    from backend.core.tools.cursor_agent import cursor_code

    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_event(ev: dict) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            args: dict = {"prompt": prompt}
            if cwd:
                args["cwd"] = cwd
            text = await cursor_code(args, context={"on_event": on_event})
            await queue.put({"type": "final", "text": text})
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    while True:
        ev = await queue.get()
        if ev is None:
            break
        yield _sse(ev)
    await task


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/api/cursor/agent")
async def cursor_agent_stream(body: CursorAgentRequest):
    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    if not settings.CURSOR_API_KEY:
        raise HTTPException(400, "CURSOR_API_KEY non configurata — impostala in Settings")
    if not rt.paid_mode or not rt.cursor_code_enabled:
        raise HTTPException(
            400,
            "Abilita paid_mode e cursor_code_enabled in /api/runtime",
        )

    prompt = body.prompt.strip()
    cwd = body.cwd or settings.JANIS_PROJECT_DIR

    async def gen():
        yield _sse({"type": "state", "state": "ACTING"})
        async for chunk in _stream_cursor_events(prompt, cwd):
            yield chunk
        yield _sse({"type": "state", "state": "IDLE"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/cursor/chat")
async def cursor_chat_stream(body: CursorChatRequest):
    """Chat ragionamento via Cursor SDK (senza tool loop JANIS)."""
    if not settings.CURSOR_API_KEY:
        raise HTTPException(400, "CURSOR_API_KEY non configurata")

    from backend.core.cursor_llm import cursor_chat

    text = body.text.strip()

    async def gen():
        yield _sse({"type": "state", "state": "THINKING"})
        try:
            if platform.system() == "Linux":
                # Delega chat Cursor a Windows CLI semplificato
                from backend.core.brain import get_session_history

                messages = get_session_history()[-10:]
                messages.append({"role": "user", "content": text})
                prompt = "\n".join(
                    f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
                )
                async for ev in _stream_cursor_events(
                    f"Rispondi in italiano come assistente JANIS.\n\n{prompt}",
                    settings.JANIS_PROJECT_DIR,
                ):
                    yield ev
            else:
                from backend.core.brain import get_session_history

                messages = list(get_session_history()[-10:])
                messages.append({"role": "user", "content": text})
                out = await cursor_chat(messages)
                step = 60
                for i in range(0, len(out), step):
                    yield _sse({"type": "chat_chunk", "text": out[i : i + step]})
                yield _sse({"type": "chat_end"})
                yield _sse({"type": "final", "text": out})
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
        yield _sse({"type": "state", "state": "IDLE"})

    return StreamingResponse(gen(), media_type="text/event-stream")
