"""Gestione processi JANIS su Windows — stop/start affidabile."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

ROOT = Path(__file__).resolve().parent.parent
PID_FILE = ROOT / "data" / "janis.pids"


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def pids_on_port(port: int) -> list[int]:
    if sys.platform != "win32":
        return []
    out = _run(
        [
            "powershell", "-NoProfile", "-Command",
            f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue)"
            f".OwningProcess | Sort-Object -Unique",
        ]
    )
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pid = int(line)
            if _pid_alive(pid):
                pids.append(pid)
    if not pids:
        netstat = _run(["netstat", "-ano"])
        for line in netstat.splitlines():
            if f":{port}" not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid > 0 and _pid_alive(pid) and pid not in pids:
                    pids.append(pid)
    return pids


def janis_process_pids() -> list[int]:
    """Trova processi Python legati a JANIS (uvicorn, launcher, shell)."""
    if sys.platform != "win32":
        return []
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
        "Where-Object { $_.CommandLine -match 'backend\\.main|desktop\\.launcher|desktop\\.shell|uvicorn' "
        "-and $_.CommandLine -match 'JANIS|backend\\.main' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps])
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def kill_pid_tree(pid: int) -> None:
    if pid <= 0:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def save_pids(pids: list[int]) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text("\n".join(str(p) for p in pids), encoding="utf-8")


def load_pids() -> list[int]:
    if not PID_FILE.exists():
        return []
    return [int(x) for x in PID_FILE.read_text(encoding="utf-8").splitlines() if x.strip().isdigit()]


def clear_pids() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def stop_all(port: int, log: logging.Logger | None = None) -> None:
    """Ferma tutti i processi JANIS e libera la porta."""
    targets: set[int] = set()
    targets.update(load_pids())
    targets.update(pids_on_port(port))
    targets.update(janis_process_pids())

    if log:
        log.info("Stop JANIS - PID target: %s", sorted(targets))

    for pid in sorted(targets):
        kill_pid_tree(pid)

    for _ in range(8):
        alive = [p for p in pids_on_port(port) if _pid_alive(p)]
        if not alive:
            break
        if log:
            log.info("Porta %s ancora occupata: %s", port, alive)
        for pid in alive:
            kill_pid_tree(pid)
        time.sleep(0.6)

    clear_pids()
    if log:
        remaining = pids_on_port(port)
        if remaining:
            log.warning("Porta %s residua: %s", port, remaining)
        else:
            log.info("Porta %s libera.", port)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def port_is_free(port: int) -> bool:
    return not any(_pid_alive(p) for p in pids_on_port(port))
