#!/usr/bin/env python3
"""Kiosk JANIS — shell open source (WebKit GTK via pywebview). Nessun login Google."""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

HUD_URL = "http://127.0.0.1:8001/server"
STATUS_URL = "http://127.0.0.1:8001/api/status"


def wait_brain(timeout_sec: int = 60) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(STATUS_URL, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    print("WARN: brain non raggiungibile, avvio HUD comunque", file=sys.stderr)


def main() -> None:
    import webview

    wait_brain()
    webview.create_window(
        "J.A.N.I.S.",
        HUD_URL,
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        text_select=False,
    )
    # Linux: GTK + WebKit2 (open source, UI solo /server)
    webview.start(gui="gtk", debug=False)


if __name__ == "__main__":
    main()
