"""Esecuzione comandi in WSL2 Ubuntu."""

from __future__ import annotations

import asyncio
import shutil

from backend.config import settings
from backend.core.agent_host import spawn_visible
from backend.core.security import validate_terminal_command
from backend.core.tools.registry import register


@register("wsl_exec")
async def wsl_exec(args: dict, context: dict | None = None) -> str:
    """Esegue comando in WSL. args: command, visible (bool), topic, cwd (path Linux)."""
    command = str(args.get("command") or "").strip()
    if not command:
        return "Errore: 'command' obbligatorio."

    try:
        validate_terminal_command(command)
    except (PermissionError, ValueError) as e:
        return f"Errore sicurezza: {e}"

    if not shutil.which("wsl.exe") and not shutil.which("wsl"):
        return "Errore: WSL non installato su questo host."

    visible = args.get("visible", False)
    topic = str(args.get("topic") or "wsl").strip()[:64]

    if visible:
        session = spawn_visible(command, topic=topic, use_wsl=True, keep_open=True)
        return f"WSL terminale visibile — agent_id={session.agent_id}\n$ {command}"

    proc = await asyncio.create_subprocess_shell(
        f'wsl.exe -e bash -lc "{command.replace(chr(34), chr(92)+chr(34))}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.TOOL_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Timeout WSL ({settings.TOOL_TIMEOUT_SEC}s): {command}"

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    parts = [f"$ wsl: {command}", f"exit: {proc.returncode}"]
    if out:
        parts.append(f"stdout:\n{out[:8000]}")
    if err:
        parts.append(f"stderr:\n{err[:4000]}")
    return "\n".join(parts)
