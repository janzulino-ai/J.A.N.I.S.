"""Tool SSH — esegue comandi sul Mac Mini (nodo remoto)."""
from __future__ import annotations

from typing import Awaitable, Callable

from backend.core.security import validate_terminal_command
from backend.core.ssh_client import mac_node_config, run_mac_ssh
from backend.core.tools.registry import register

EventCallback = Callable[[dict], Awaitable[None]]


async def _emit_mac_panel(on_event: EventCallback | None, text: str) -> None:
    if not on_event:
        return
    await on_event({
        "type": "panel",
        "action": "append",
        "id": "mac-main",
        "panel_type": "mac",
        "content": text,
    })


@register("mac_ssh")
async def mac_ssh(args: dict, context: dict | None = None) -> str:
    """
    Esegue un comando shell sul Mac Mini via SSH (chiave in ~/.ssh/id_ed25519).

    args:
      command (required)
      cwd — directory remota opzionale
    """
    command = (args.get("command") or "").strip()
    if not command:
        return "Errore: 'command' obbligatorio."

    cfg = mac_node_config()
    if not cfg["enabled"]:
        return (
            "Mac SSH disabilitato. In .env: MAC_SSH_ENABLED=1, "
            f"MAC_SSH_HOST={cfg.get('host') or 'mac-mini-di-janzu.local'}"
        )

    try:
        validate_terminal_command(command)
    except (PermissionError, ValueError) as e:
        return f"Errore sicurezza: {e}"

    ctx = context or {}
    on_event: EventCallback | None = ctx.get("on_event")

    if on_event:
        await on_event({
            "type": "panel",
            "action": "open",
            "id": "mac-main",
            "panel_type": "mac",
            "title": cfg.get("label") or "Mac Mini",
            "width": 520,
            "height": 360,
            "manual": True,
        })

    cwd = (args.get("cwd") or "").strip() or None
    header = f"[Mac {cfg['user']}@{cfg['host']}] $ {command}\n"
    await _emit_mac_panel(on_event, header)

    try:
        code, out, err = await run_mac_ssh(command, cwd=cwd)
    except TimeoutError as e:
        msg = str(e)
        await _emit_mac_panel(on_event, msg + "\n")
        return msg
    except Exception as e:
        msg = f"Errore SSH Mac: {e}"
        await _emit_mac_panel(on_event, msg + "\n")
        return msg

    body = ""
    if out:
        body += out if out.endswith("\n") else out + "\n"
    if err:
        body += f"stderr:\n{err}\n"
    body += f"exit: {code}\n"
    await _emit_mac_panel(on_event, body)

    parts = [header.strip(), f"exit: {code}"]
    if out.strip():
        parts.append(f"stdout:\n{out.strip()[:8000]}")
    if err.strip():
        parts.append(f"stderr:\n{err.strip()[:4000]}")
    return "\n".join(parts)
