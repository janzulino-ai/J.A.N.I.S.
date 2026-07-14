"""Controllo VM win-vm via libvirt (virsh)."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.WinVM")

_VM_NAME = settings.WIN_VM_NAME


def _virsh(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    if not shutil.which("virsh"):
        return 127, "", "virsh non installato"
    try:
        proc = subprocess.run(
            ["virsh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout virsh"
    except Exception as exc:
        return 1, "", str(exc)


async def _virsh_async(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    return await asyncio.to_thread(_virsh, *args, timeout=timeout)


def _parse_dominfo(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


async def vm_status() -> dict[str, Any]:
    """Stato VM + VNC."""
    code, out, err = await _virsh_async("dominfo", _VM_NAME)
    if code != 0:
        return {
            "name": _VM_NAME,
            "available": False,
            "state": "undefined",
            "error": err or out or "VM non definita",
            "vnc": vnc_info(),
        }
    info = _parse_dominfo(out)
    disk = ""
    code2, xml, _ = await _virsh_async("dumpxml", _VM_NAME)
    if code2 == 0:
        m = re.search(r"source dev='([^']+)'", xml)
        if m:
            disk = m.group(1)
    return {
        "name": _VM_NAME,
        "available": True,
        "state": info.get("state", "unknown").lower(),
        "autostart": info.get("autostart", "?"),
        "disk": disk,
        "vnc": vnc_info(),
    }


def vnc_info() -> dict[str, Any]:
    return {
        "host": settings.WIN_VM_VNC_HOST,
        "port": settings.WIN_VM_VNC_PORT,
        "ws_path": "/ws/vnc",
        "page": "/windows",
    }


async def vm_start() -> dict[str, Any]:
    code, out, err = await _virsh_async("start", _VM_NAME)
    if code != 0 and "already active" not in (err + out).lower():
        return {"ok": False, "error": err or out}
    st = await vm_status()
    return {"ok": True, "state": st.get("state")}


async def vm_stop() -> dict[str, Any]:
    code, out, err = await _virsh_async("destroy", _VM_NAME)
    if code != 0:
        return {"ok": False, "error": err or out}
    return {"ok": True, "state": "shut off"}


async def vm_reboot() -> dict[str, Any]:
    code, out, err = await _virsh_async("reboot", _VM_NAME)
    if code != 0:
        await vm_stop()
        return await vm_start()
    return {"ok": True, "state": "running"}
