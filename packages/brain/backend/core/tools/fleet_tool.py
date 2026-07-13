"""Tool Fleet — esecuzione remota su nodi (Fase 2)."""
from __future__ import annotations

from backend.core.fleet.manager import fleet_manager
from backend.core.tools.registry import register


@register("fleet_execute")
async def fleet_execute(args: dict) -> str:
    """Esegue un comando shell su un nodo Fleet connesso.

    args: node_id (obbligatorio), command (obbligatorio), cwd opzionale
    """
    node_id = (args.get("node_id") or args.get("node") or "").strip().lower()
    command = (args.get("command") or "").strip()
    cwd = (args.get("cwd") or "").strip()
    if not node_id or not command:
        return "Errore: node_id e command obbligatori."

    result = await fleet_manager.execute_command(node_id, command, cwd=cwd)
    if not result.get("ok"):
        return f"Fleet execute fallito: {result.get('error', 'errore')}"

    out = (result.get("stdout") or "").strip()
    err = (result.get("stderr") or "").strip()
    code = result.get("exit_code")
    lines = [f"Nodo {node_id} — exit {code}"]
    if out:
        lines.append(out[:8000])
    if err:
        lines.append(f"stderr:\n{err[:2000]}")
    return "\n".join(lines) if len(lines) > 1 else lines[0]
