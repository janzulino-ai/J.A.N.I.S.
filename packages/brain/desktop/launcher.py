"""Avvio JANIS — backend nascosto + shell Chromium."""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


def _setup_logging(console: bool) -> logging.Logger:
    log = logging.getLogger("JANIS.Launcher")
    log.handlers.clear()
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_DIR / "launcher.log", encoding="utf-8", mode="a")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if console:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    return log


def _wait_backend(port: int, backend: subprocess.Popen, timeout: float = 60.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/status"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if backend.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if "JANIS" in r.read().decode("utf-8"):
                    from desktop.process_util import pids_on_port
                    owners = pids_on_port(port)
                    if backend.pid in owners or not owners:
                        return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def run_app(*, console: bool = False, reload: bool = False, window: bool = False, widget: bool = True, overlay: bool = False) -> int:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("PYTHONPATH", str(ROOT))

    from backend.config import settings
    from desktop.process_util import port_is_free, save_pids, stop_all

    log = _setup_logging(console)
    port = settings.PORT

    log.info("=== Avvio JANIS (console=%s, reload=%s) ===", console, reload)

    stop_all(port, log)
    if not port_is_free(port):
        log.error("Impossibile liberare porta %s - riprova dev/stop-janis.ps1", port)
        if not console:
            _show_error(f"Porta {port} occupata.\nEsegui dev\\stop-janis.ps1")
        return 1

    backend_log_path = LOG_DIR / "backend.log"
    backend_log = open(backend_log_path, "a", encoding="utf-8")
    backend_log.write(f"\n--- session {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    backend_log.flush()

    bind_host = settings.HOST or "0.0.0.0"
    cmd = [
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", bind_host, "--port", str(port),
        "--log-level", "info",
    ]
    if reload:
        cmd.extend([
            "--reload",
            "--reload-dir", str(ROOT / "backend"),
            "--reload-dir", str(ROOT / "frontend"),
        ])

    popen_kw: dict = {
        "cwd": str(ROOT),
        "env": {**os.environ, "PYTHONPATH": str(ROOT)},
        "stdout": backend_log,
        "stderr": subprocess.STDOUT,
    }
    if not console and sys.platform == "win32":
        popen_kw["creationflags"] = CREATE_NO_WINDOW

    backend = subprocess.Popen(cmd, **popen_kw)
    save_pids([backend.pid, os.getpid()])
    log.info("Backend PID %s -> %s", backend.pid, backend_log_path)

    try:
        if not _wait_backend(port, backend):
            tail = ""
            try:
                tail = backend_log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
            except Exception:
                pass
            log.error("Backend non avviato. Ultimo log:\n%s", tail)
            if not console:
                _show_error("JANIS: backend non avviato.\nControlla data\\backend.log")
            return 1

        log.info("Backend OK - apro shell Chromium (WebView2)")
        from desktop.shell import JanisDesktop

        JanisDesktop(
            base_url=f"http://127.0.0.1:{port}",
            window_mode=window,
            widget_mode=widget,
            overlay_mode=overlay,
        ).run()
        log.info("Shell chiusa.")
        return 0
    except Exception as e:
        log.exception("Errore launcher: %s", e)
        if not console:
            _show_error(f"JANIS errore avvio:\n{e}")
        return 1
    finally:
        log.info("Arresto JANIS...")
        backend.terminate()
        try:
            backend.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass
        backend_log.close()
        stop_all(port, log)


def _show_error(msg: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "JANIS", 0x10)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="JANIS launcher")
    parser.add_argument("--console", action="store_true", help="Log nel terminale (debug)")
    parser.add_argument("--reload", action="store_true", help="Hot-reload (puo complicare il riavvio)")
    parser.add_argument("--window", action="store_true", help="IDE completa")
    parser.add_argument("--widget", action="store_true", help="Chat widget (default)")
    parser.add_argument("--overlay", action="store_true", help="Overlay fullscreen")
    args = parser.parse_args()
    widget = not args.window and not args.overlay
    if args.widget:
        widget = True
    code = run_app(
        console=args.console,
        reload=args.reload,
        window=args.window,
        widget=widget,
        overlay=args.overlay,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
