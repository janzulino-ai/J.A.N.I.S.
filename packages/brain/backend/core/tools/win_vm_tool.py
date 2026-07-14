"""Tool win-vm — avvio/stop VM Windows on demand."""
from __future__ import annotations

import json

from backend.core.tools.registry import register


@register("win_vm")
async def win_vm_tool(args: dict) -> str:
    """
    Gestisce VM Windows (KVM/virsh) sul server.
    args.action: status | start | stop | reboot
    """
    from backend.core import win_vm

    action = (args.get("action") or "status").lower().strip()
    if action == "start":
        result = await win_vm.vm_start()
    elif action == "stop":
        result = await win_vm.vm_stop()
    elif action == "reboot":
        result = await win_vm.vm_reboot()
    elif action == "status":
        result = await win_vm.vm_status()
    else:
        return f"Azione '{action}' non valida. Usa: status, start, stop, reboot."

    st = result if isinstance(result, dict) else {"result": result}
    if action == "start" and st.get("ok"):
        vnc = (await win_vm.vm_status()).get("vnc") or {}
        return (
            f"VM avviata · stato {st.get('state', '?')}\n"
            f"VNC: {vnc.get('host')}:{vnc.get('port')} · pagina {vnc.get('page')}"
        )
    if action == "status":
        lines = [
            f"VM {st.get('name', '?')}: {st.get('state', '?')}",
            f"Disponibile: {'sì' if st.get('available') else 'no'}",
        ]
        if st.get("error"):
            lines.append(f"Errore: {st['error']}")
        if st.get("disk"):
            lines.append(f"Disco: {st['disk']}")
        vnc = st.get("vnc") or {}
        if vnc:
            lines.append(f"VNC {vnc.get('host')}:{vnc.get('port')} · {vnc.get('page')}")
        return "\n".join(lines)
    return json.dumps(st, ensure_ascii=False, indent=2)
