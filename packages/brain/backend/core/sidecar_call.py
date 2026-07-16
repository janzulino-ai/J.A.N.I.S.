"""Helper: chiama MCP sidecar o CLI, con messaggio degradato se assente."""
from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Any

logger = logging.getLogger("JANIS.Sidecar")


async def call_mcp(
    server: str,
    tool: str,
    arguments: dict | None = None,
    *,
    timeout: float | None = None,
) -> str | None:
    """Ritorna testo risultato o None se server/tool non disponibili."""
    try:
        from backend.core.mcp_client import call_mcp_tool, mcp_enabled

        if not mcp_enabled():
            return None
        return await call_mcp_tool(server, tool, arguments or {}, timeout=timeout)
    except Exception as e:
        logger.info("MCP %s/%s non disponibile: %s", server, tool, e)
        return None


async def run_cli(
    command: str,
    args: list[str],
    *,
    timeout: float = 120.0,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Esegue CLI se presente nel PATH. Exit -1 se comando assente."""
    resolved = shutil.which(command)
    if not resolved:
        return -1, "", f"comando '{command}' non trovato nel PATH"
    try:
        proc = await asyncio.create_subprocess_exec(
            resolved,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            proc.returncode or 0,
            (stdout or b"").decode("utf-8", errors="replace"),
            (stderr or b"").decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        return -2, "", f"timeout {timeout}s"
    except Exception as e:
        return -3, "", str(e)


def missing_sidecar(name: str, install_hint: str) -> str:
    return (
        f"Sidecar '{name}' non disponibile.\n"
        f"Install: {install_hint}\n"
        f"Poi verifica con tool janis_doctor o mcp_status."
    )


def pick_mcp_tool(tools: list[dict[str, Any]], *candidates: str) -> str | None:
    names = {(t.get("name") or "").strip() for t in tools if isinstance(t, dict)}
    for c in candidates:
        if c in names:
            return c
    # fuzzy: substring
    for c in candidates:
        for n in names:
            if c in n or n in c:
                return n
    return next(iter(names), None) if names else None
