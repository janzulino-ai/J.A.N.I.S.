"""Diagnostica connettività Fleet — hub WebSocket sul coordinatore Windows."""
from __future__ import annotations

import re
import socket
import subprocess
import sys
from typing import Any

_FLEET_ISSUE_RE = re.compile(
    r"10061|connection refused|rifiuto persistente|ws/fleet-node|"
    r"websocket.*8001|fleet.*(offline|connessione|connect)",
    re.IGNORECASE,
)

_FLEET_ENV_BLAME_RE = re.compile(
    r"ambiente operativo|solo firewall|problema di rete|"
    r"canale di comunicazione.*blocc",
    re.IGNORECASE,
)


def looks_like_fleet_connection_issue(text: str, user_text: str = "") -> bool:
    combined = f"{user_text} {text}"
    if _FLEET_ISSUE_RE.search(combined):
        return True
    if not user_text or not _FLEET_ENV_BLAME_RE.search(text or ""):
        return False
    lower = user_text.lower()
    return any(
        k in lower
        for k in ("fleet", "8001", "websocket", "mac mini", "bridge", "nodo", "10061", "flotta")
    )


def _parse_listening_addresses(port: int) -> list[str]:
    lines: list[str] = []
    needle = f":{port}"
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return lines
    for line in out.splitlines():
        if "LISTENING" not in line or needle not in line:
            continue
        lines.append(line.strip())
    return lines


def _listening_on_all_interfaces(port: int, lines: list[str]) -> bool:
    for line in lines:
        if f"0.0.0.0:{port}" in line.replace(" ", ""):
            return True
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("TCP", "TCPv6"):
            local = parts[1]
            if local.endswith(f":{port}") and not local.startswith("127.") and local != f"[::1]:{port}":
                return True
    return False


def diag_fleet_hub(port: int = 8001) -> dict[str, Any]:
    listening = _parse_listening_addresses(port)
    if not listening:
        return {
            "check": f"fleet_hub:{port}",
            "ok": False,
            "listening": [],
            "localhost_only": False,
            "detail": "Backend non in ascolto sulla porta",
        }

    on_all = _listening_on_all_interfaces(port, listening)
    localhost_only = bool(listening) and not on_all and any("127.0.0.1" in ln for ln in listening)
    return {
        "check": f"fleet_hub:{port}",
        "ok": on_all,
        "listening": listening[:5],
        "localhost_only": localhost_only,
        "detail": "; ".join(listening[:3]),
    }


def ensure_windows_firewall_rule(port: int, name: str | None = None) -> dict[str, Any]:
    if sys.platform != "win32":
        return {"check": "firewall", "ok": True, "detail": "non-Windows, skip"}
    rule_name = name or f"JANIS Fleet TCP {port}"
    try:
        show = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if show.returncode == 0 and "No rules" not in (show.stdout or ""):
            return {"check": "firewall", "ok": True, "detail": f"Regola presente: {rule_name}"}

        add = subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        detail = (add.stdout or add.stderr or "").strip() or f"exit {add.returncode}"
        return {"check": "firewall", "ok": add.returncode == 0, "detail": detail}
    except Exception as e:  # noqa: BLE001
        return {"check": "firewall", "ok": False, "detail": str(e)}


def local_lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "IP-LOCALE"
