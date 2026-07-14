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
    screen_w, screen_h = 1920, 1080
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        display = Gdk.Display.get_default()
        if display:
            mon = display.get_primary_monitor() or display.get_monitor(0)
            if mon:
                geo = mon.get_geometry()
                scale = mon.get_scale_factor()
                screen_w = geo.width * scale
                screen_h = geo.height * scale
    except Exception:
        pass

    webview.create_window(
        "J.A.N.I.S.",
        HUD_URL,
        width=screen_w,
        height=screen_h,
        x=0,
        y=0,
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        text_select=False,
        zoomable=False,
    )
    # Linux: GTK + WebKit2 (open source, UI solo /server)
    webview.start(gui="gtk", debug=False)


if __name__ == "__main__":
    main()
