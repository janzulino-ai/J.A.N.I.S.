"""Diagnostica layer desktop JANIS."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from desktop.wallpaper import find_workerw, find_hwnd_by_pid, attach_wallpaper_process


def main():
    print("=== JANIS Desktop Layer Diagnostic ===")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    for mod in ("webview", "win32gui", "uvicorn", "fastapi"):
        try:
            __import__(mod)
            print(f"  [OK] {mod}")
        except ImportError:
            print(f"  [MISSING] {mod}")

    try:
        w = find_workerw()
        print(f"WorkerW HWND: {w}")
    except Exception as e:
        print(f"WorkerW ERROR: {e}")

    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8001/api/status", timeout=3)
        print("Backend: OK (localhost:8001)")
    except Exception as e:
        print(f"Backend: OFFLINE ({e})")

    pid = os.getpid()
    print(f"\nCerca finestre processo corrente (pid={pid})...")
    try:
        import win32gui
        import win32process

        def cb(hwnd, _):
            _, p = win32process.GetWindowThreadProcessId(hwnd)
            if p == pid:
                print(f"  hwnd={hwnd} title={win32gui.GetWindowText(hwnd)!r} class={win32gui.GetClassName(hwnd)}")
            return True

        win32gui.EnumWindows(cb, None)
    except ImportError:
        print("  pywin32 non disponibile")

    print("\nPer test visivo: python -m desktop.wallpaper_host")
    print("(richiede backend attivo)")


if __name__ == "__main__":
    main()
