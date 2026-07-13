import asyncio
import os

from backend.config import settings
from backend.core.security import validate_cwd, validate_terminal_command
from backend.core.tools.registry import register


@register("terminal")
async def run_terminal(args: dict) -> str:
    command = str(args.get("command") or "").strip()
    if not command:
        return "Errore: 'command' obbligatorio."

    try:
        validate_terminal_command(command)
        cwd = validate_cwd(args.get("cwd"))
    except (PermissionError, ValueError, FileNotFoundError) as e:
        return f"Errore sicurezza: {e}"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        return f"Errore avvio comando ({type(e).__name__}): {e}"

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.TOOL_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return f"Timeout ({settings.TOOL_TIMEOUT_SEC}s) per: {command}"
    except Exception as e:
        proc.kill()
        return f"Errore esecuzione comando ({type(e).__name__}): {e}"

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    code = proc.returncode

    parts = [f"$ {command}", f"exit: {code}"]
    if out:
        parts.append(f"stdout:\n{out[:8000]}")
    if err:
        parts.append(f"stderr:\n{err[:4000]}")
    return "\n".join(parts)
