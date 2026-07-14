"""API dashboard HUD kiosk."""
from __future__ import annotations

import asyncio
import os
import shutil

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core.hud_dashboard import build_dashboard
from backend.core.security import validate_terminal_command
from backend.core.tools.registry import execute_tool

router = APIRouter()


class HudTerminalRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    shell: str = Field(default="wsl", pattern="^(wsl|win|brain)$")


async def _run_win_powershell(command: str) -> str:
    validate_terminal_command(command)
    ps_candidates = [
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "powershell.exe",
        "powershell",
    ]
    ps = next((p for p in ps_candidates if os.path.isfile(p) or shutil.which(p)), None)
    if not ps:
        return "Errore: PowerShell non trovato su questo host."
    safe = command.replace('"', '\\"')
    proc = await asyncio.create_subprocess_shell(
        f'"{ps}" -NoProfile -NonInteractive -Command "{safe}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.TOOL_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Timeout ({settings.TOOL_TIMEOUT_SEC}s): {command}"
    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    parts = [f"$ powershell: {command}", f"exit: {proc.returncode}"]
    if out:
        parts.append(f"stdout:\n{out[:8000]}")
    if err:
        parts.append(f"stderr:\n{err[:4000]}")
    return "\n".join(parts)


@router.get("/api/hud/dashboard")
async def hud_dashboard(refresh_inventory: bool = Query(default=False)):
    return await build_dashboard(refresh_inventory=refresh_inventory)


@router.post("/api/hud/terminal")
async def hud_terminal(body: HudTerminalRequest):
    cmd = body.command.strip()
    if not cmd:
        return {"ok": False, "error": "comando vuoto"}
    try:
        if body.shell == "win":
            output = await _run_win_powershell(cmd)
        elif body.shell == "wsl" and shutil.which("wsl.exe"):
            output = await execute_tool("wsl_exec", {"command": cmd})
        else:
            output = await execute_tool("terminal", {"command": cmd})
        return {"ok": True, "output": output, "shell": body.shell}
    except Exception as e:
        return {"ok": False, "error": str(e)}
