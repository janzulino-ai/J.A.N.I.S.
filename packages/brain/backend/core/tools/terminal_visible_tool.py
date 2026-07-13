"""Terminale OS visibile — modello Cursor."""

from __future__ import annotations

from backend.core.agent_host import is_heavy_command, spawn_visible
from backend.core.security import validate_cwd, validate_terminal_command
from backend.core.tools.registry import register


@register("terminal_visible")
async def terminal_visible(args: dict, context: dict | None = None) -> str:
    """Apre finestra terminale visibile (wt.exe / WSL). args: command, topic, cwd, use_wsl."""
    command = str(args.get("command") or "").strip()
    if not command:
        return "Errore: 'command' obbligatorio."

    try:
        validate_terminal_command(command)
        cwd = validate_cwd(args.get("cwd"))
    except (PermissionError, ValueError, FileNotFoundError) as e:
        return f"Errore sicurezza: {e}"

    topic = str(args.get("topic") or "agent").strip()[:64] or "agent"
    use_wsl = bool(args.get("use_wsl"))
    keep_open = args.get("keep_open", True) is not False

    session = spawn_visible(
        command,
        topic=topic,
        cwd=cwd,
        use_wsl=use_wsl,
        keep_open=keep_open,
    )
    return (
        f"Terminale visibile aperto — agent_id={session.agent_id}, topic={topic}, "
        f"pid={session.pid}, title={session.title}\n"
        f"$ {command}"
    )


@register("terminal_smart")
async def terminal_smart(args: dict, context: dict | None = None) -> str:
    """Esegue in visibile se comando pesante, altrimenti delega a terminal nascosto."""
    command = str(args.get("command") or "").strip()
    if is_heavy_command(command):
        return await terminal_visible(args, context)
    from backend.core.tools.terminal import run_terminal

    return await run_terminal(args)
