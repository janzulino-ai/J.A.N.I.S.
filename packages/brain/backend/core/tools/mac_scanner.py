"""Scansione progetti Mac via SSH — tool registrato."""
from __future__ import annotations

import json

from backend.core.mac_knowledge import get_mac_knowledge_status, scan_and_learn_mac_projects
from backend.core.tools.registry import register


@register("scan_mac_projects")
async def scan_mac_projects_tool(args: dict) -> str:
    """
    Scansiona progetti Cursor sul Mac Mini via SSH e impara con Ollama.

    args:
      scan_root — directory remota (default ~/Documents)
      learn — bool, default true (arricchimento Ollama + memoria)
    """
    scan_root = (args.get("scan_root") or "").strip() or None
    learn = args.get("learn", True)
    if str(learn).lower() in ("0", "false", "no"):
        learn = False

    result = await scan_and_learn_mac_projects(scan_root=scan_root, learn=learn)
    if not result.get("ok"):
        return f"Errore scan Mac: {result.get('error', 'sconosciuto')}"

    lines = [
        f"Scan Mac completato: {result.get('count', 0)} progetti in {result.get('scan_root', '~/Documents')}",
    ]
    for p in (result.get("projects") or [])[:12]:
        stacks = ", ".join(p.get("stack_files") or []) or "—"
        flags = []
        if p.get("has_git"):
            flags.append("git")
        if p.get("has_cursor"):
            flags.append(".cursor")
        flag_s = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- {p.get('name')}: {p.get('path')} ({stacks}){flag_s}")

    if result.get("learned"):
        lines.append("")
        lines.append(f"Apprendimento: {result.get('memories_created', 0)} memorie/neuroni creati.")
        if result.get("summary"):
            lines.append(f"Sintesi: {result['summary'][:400]}")
    elif learn:
        lines.append("\nNessun progetto da apprendere.")

    return "\n".join(lines)


@register("mac_projects_status")
async def mac_projects_status(args: dict) -> str:
    """Stato ultima scansione progetti Mac."""
    return json.dumps(get_mac_knowledge_status(), ensure_ascii=False, indent=2)
