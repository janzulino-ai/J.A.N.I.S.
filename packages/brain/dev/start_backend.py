"""Dev entry — solo backend API (senza UI). Per la shell usa dev/start_app.py."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def _pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return []
    pids: set[int] = set()
    needle = f":{port}"
    for line in out.splitlines():
        if "LISTENING" not in line or needle not in line:
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            pid = int(parts[-1])
            if _pid_alive(pid):
                pids.add(pid)
    return sorted(pids)


def _janis_status(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as resp:
            import json
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def _janis_running(port: int) -> bool:
    st = _janis_status(port)
    return bool(st and st.get("service") == "JANIS")


def _needs_restart(port: int) -> bool:
    """True se JANIS risponde ma è una build vecchia (senza brain_version 3)."""
    st = _janis_status(port)
    if not st:
        return bool(_pids_on_port(port))
    return st.get("brain_version", 0) < 5


def _stop_port_listeners(port: int) -> None:
    for pid in _pids_on_port(port):
        if pid <= 0 or pid == os.getpid():
            continue
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            check=False,
            capture_output=True,
        )
        print(f"  Chiuso processo PID {pid} sulla porta {port}")
    time.sleep(0.8)


def _port_bindable(host: str, port: int) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _pick_port(host: str, preferred: int) -> int:
    if _port_bindable(host, preferred):
        return preferred
    _stop_port_listeners(preferred)
    time.sleep(0.8)
    if _port_bindable(host, preferred):
        return preferred
    for alt in (8010, 8020, 8030, 8040):
        if alt != preferred and _port_bindable(host, alt):
            print(f"Porta {preferred} bloccata (socket fantasma?) — avvio su :{alt}")
            return alt
    return preferred


if __name__ == "__main__":
    from backend.config import settings

    host = settings.HOST or "0.0.0.0"
    port = settings.PORT

    if _needs_restart(port):
        reason = "build vecchia" if _janis_running(port) else "porta occupata"
        print(f"Porta {port} — {reason}, riavvio backend dev...")
        _stop_port_listeners(port)
        time.sleep(1.2)

    port = _pick_port(host, port)
    if not _port_bindable(host, port):
        print(f"\nERRORE: nessuna porta libera (provato {settings.PORT}, 8010-8040). Riavvia il PC.")
        sys.exit(1)

    import uvicorn

    print(f"JANIS API dev -> http://127.0.0.1:{port}")
    if port != settings.PORT:
        print(f"Browser: http://127.0.0.1:{port}/?mode=browser")
    print("Solo backend. Per l'app: python dev/start_app.py  oppure F5 'JANIS App'")
    print("Se la chat ignora la memoria: Shift+F5 in Cursor, poi F5 (brain_version 5)")
    try:
        uvicorn.run(
            "backend.main:app",
            host=host,
            port=port,
            reload=False,
        )
    except OSError as e:
        fallback = 8010 if port == 8001 else None
        if fallback and "10048" in str(e):
            print(f"\nPorta {port} bloccata — avvio su :{fallback}")
            print(f"Browser: http://127.0.0.1:{fallback}/?mode=browser")
            uvicorn.run(
                "backend.main:app",
                host=host,
                port=fallback,
                reload=False,
            )
        else:
            print(f"\nERRORE avvio server: {e}")
            print("Prova: .\\dev\\stop-janis.ps1  poi riavvia.")
            sys.exit(1)
