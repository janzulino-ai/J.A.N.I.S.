"""Dev entry — backend + finestra desktop (simulatore app nativa)."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))


def _wait_backend(port: int, timeout: float = 60.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/status"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def _run_backend(port: int, host: str) -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    from backend.config import settings

    port = settings.PORT
    host = settings.HOST or "0.0.0.0"
    print(f"Avvio backend JANIS su {host}:{port}...")
    backend = threading.Thread(target=_run_backend, args=(port, host), daemon=True)
    backend.start()

    if not _wait_backend(port):
        print("ERRORE: backend non risponde")
        sys.exit(1)

    print("Avvio shell desktop (finestra)...")
    from desktop.shell import main as desktop_main

    sys.argv = ["desktop.shell", "--window"]
    desktop_main()
