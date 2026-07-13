"""
JANIS — overlay fullscreen sopra il sistema operativo.
Finestra trasparente a tutto schermo, sempre in primo piano.
Click-through attivo di default (usi il PC normalmente).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] JANIS.Desktop: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "desktop.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("JANIS.Desktop")

DEFAULT_URL = "http://127.0.0.1:8001"
WINDOW_TITLE = "JANIS"
# Motore Chromium via WebView2 (Edge Chromium) — non usa browser esterno
CHROMIUM_GUI = "edgechromium"
USER_AGENT = "JANIS/2.0 (Chromium/WebView2; Windows)"


class JanisShellApi:
    """Bridge JS ↔ Python per azioni desktop (browser di sistema, ecc.)."""

    def open_url(self, url: str) -> dict:
        from backend.core.open_url import open_system_url

        try:
            opened = open_system_url(url)
            logger.info("Shell API — browser: %s", opened)
            return {"ok": True, "url": opened}
        except ValueError as e:
            return {"ok": False, "error": str(e)}


class JanisDesktop:
    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        *,
        window_mode: bool = False,
        widget_mode: bool = True,
        overlay_mode: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.window_mode = window_mode
        self.widget_mode = widget_mode and not window_mode and not overlay_mode
        self.overlay_mode = overlay_mode and not window_mode
        self.muted = False
        self.click_through = False
        self._window = None
        self._webview = None
        self._tray = None
        self._running = True
        self._hwnd: int | None = None
        self._pid = os.getpid()

    def _api(self, path: str, method: str = "GET", body: dict | None = None, timeout: float = 5) -> dict | None:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            import json

            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                import json

                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            logger.debug("API %s failed: %s", path, e)
            return None

    def wait_for_backend(self, timeout: float = 90.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            # /api/status può essere lento (SSH Mac); presence basta per il ping
            if self._api("/api/presence", timeout=12):
                return True
            time.sleep(1.5)
        return False

    def _page_url(self) -> str:
        if self.widget_mode:
            return f"{self.base_url}/brain?device_id=desktop"
        mode = "window" if self.window_mode else "fullscreen"
        return f"{self.base_url}/?mode={mode}&muted={'1' if self.muted else '0'}"

    def _apply_click_through(self, enabled: bool) -> None:
        self.click_through = enabled
        if self._hwnd:
            from desktop.overlay import set_click_through

            set_click_through(self._hwnd, enabled)
        if self._window:
            try:
                self._window.evaluate_js(
                    f"window.JANIS?.setInteractMode?.({str(not enabled).lower()})"
                )
            except Exception:
                pass
        logger.info("Click-through: %s", "ON" if enabled else "OFF")

    def set_visible(self, visible: bool) -> None:
        if not self._window:
            return
        if visible:
            self._window.show()
            if self._hwnd:
                from desktop.overlay import set_topmost

                set_topmost(self._hwnd)
        else:
            self._window.hide()

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        self._api("/api/desktop/mode", "POST", {"mode": "overlay"})
        self._api("/api/desktop/mute", "POST", {"muted": muted})
        if self._window:
            try:
                self._window.evaluate_js(f"window.JANIS?.setMuted?.({str(muted).lower()})")
            except Exception:
                pass

    def _setup_overlay_hwnd(self) -> None:
        from desktop.overlay import configure_fullscreen_overlay

        self._hwnd = configure_fullscreen_overlay(
            self._pid, WINDOW_TITLE, click_through=self.click_through,
        )

    def _make_tray_icon(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, 56, 56), fill=(0, 212, 255, 255))
        draw.text((22, 20), "J", fill=(0, 20, 40, 255))
        return img

    def _build_tray(self):
        import pystray
        from pystray import MenuItem as Item

        def on_show(_icon, _item):
            self.set_visible(True)

        def on_interact(_icon, _item):
            self._apply_click_through(False)

        def on_passive(_icon, _item):
            self._apply_click_through(True)

        def on_hide(_icon, _item):
            self.set_visible(False)

        def on_mute(_icon, _item):
            self.set_muted(not self.muted)

        def on_quit(_icon, _item):
            self._running = False
            if self._tray:
                self._tray.stop()
            if self._webview:
                self._webview.destroy()
            os._exit(0)

        def on_ide(_icon, _item):
            import subprocess
            import sys
            subprocess.Popen(
                [sys.executable, "-m", "desktop.shell", "--window", "--url", self.base_url],
                cwd=str(ROOT),
            )

        def on_wallpaper(_icon, _item):
            import subprocess
            import sys
            subprocess.Popen(
                [sys.executable, "-m", "desktop.wallpaper_host", "--url", self.base_url],
                cwd=str(ROOT),
            )
            self._api("/api/presence/claim", "POST", {"device_id": "desktop", "surface": "wallpaper", "follow_user": True})

        def on_agents(_icon, _item):
            data = self._api("/api/agents/sessions") or {}
            n = len(data.get("sessions") or [])
            logger.info("Agenti attivi: %d", n)

        menu_items = [
            Item("Mostra brain", on_show, default=True),
            Item("IDE completa", on_ide),
            Item("Agenti terminali", on_agents),
            Item("Sfondo WorkerW", on_wallpaper),
            Item("Nascondi", on_hide),
            Item(lambda _: f"Mute: {'ON' if self.muted else 'OFF'}", on_mute),
            Item("Esci", on_quit),
        ]
        if self.overlay_mode:
            menu_items = [
                Item("Mostra overlay", on_show, default=True),
                Item("Interagisci", on_interact),
                Item("Pass-through", on_passive),
                Item("Nascondi", on_hide),
                Item(lambda _: f"Mute: {'ON' if self.muted else 'OFF'}", on_mute),
                Item("Esci", on_quit),
            ]
        menu = pystray.Menu(*menu_items)
        self._tray = pystray.Icon("JANIS", self._make_tray_icon(), "J.A.N.I.C.E.", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def run_pywebview(self) -> None:
        import webview

        if self.widget_mode:
            screen = webview.screens[0] if webview.screens else None
            sw = screen.width if screen else 1920
            sh = screen.height if screen else 1080
            self._window = webview.create_window(
                "JANIS Brain",
                self._page_url(),
                width=128,
                height=128,
                x=max(20, sw - 148),
                y=max(20, sh - 168),
                frameless=True,
                transparent=True,
                on_top=True,
                easy_drag=True,
                resizable=False,
                min_size=(128, 128),
                background_color="#000000",
                js_api=JanisShellApi(),
            )
            self._api("/api/desktop/mode", "POST", {"mode": "overlay"})
            self._api(
                "/api/presence/claim",
                "POST",
                {"device_id": "desktop", "surface": "widget", "follow_user": True},
            )
            self._webview = webview
            self._build_tray()
            logger.info("JANIS brain — %s", self._page_url())
            webview.start(gui=CHROMIUM_GUI, debug=False)
            return

        if self.window_mode:
            self._window = webview.create_window(
                WINDOW_TITLE,
                self._page_url(),
                width=1280,
                height=820,
                x=80,
                y=40,
                frameless=True,
                transparent=True,
                on_top=False,
                easy_drag=True,
                resizable=True,
                fullscreen=False,
                min_size=(960, 640),
                background_color="#000000",
                js_api=JanisShellApi(),
            )
            self._api("/api/desktop/mode", "POST", {"mode": "window"})
            self._webview = webview
            self._build_tray()
            logger.info("JANIS shell Chromium (WebView2) — %s", self._page_url())

            def _inject_ua():
                try:
                    self._window.evaluate_js(
                        f'Object.defineProperty(navigator, "userAgent", {{get: () => "{USER_AGENT}"}});'
                    )
                except Exception:
                    pass

            if hasattr(self._window.events, "loaded"):
                self._window.events.loaded += lambda: _inject_ua()

            webview.start(gui=CHROMIUM_GUI, debug=False)
            return

        screen = webview.screens[0] if webview.screens else None
        sw = screen.width if screen else 1920
        sh = screen.height if screen else 1080

        self._window = webview.create_window(
            WINDOW_TITLE,
            self._page_url(),
            width=sw,
            height=sh,
            x=0,
            y=0,
            frameless=True,
            transparent=True,
            on_top=True,
            easy_drag=False,
            resizable=False,
            fullscreen=True,
            background_color="#000000",
            js_api=JanisShellApi(),
        )

        def on_loaded():
            def setup():
                self._setup_overlay_hwnd()
                self._apply_click_through(False)

            threading.Timer(1.5, setup).start()
            try:
                self._window.evaluate_js("window.JANIS?.setInteractMode?.(true)")
            except Exception:
                pass

        self.click_through = False

        self._window.events.loaded += on_loaded

        self._api("/api/desktop/mode", "POST", {"mode": "overlay"})
        self._webview = webview
        self._build_tray()
        logger.info("JANIS overlay Chromium (WebView2) — %s", self._page_url())
        webview.start(gui=CHROMIUM_GUI, debug=False)

    def run(self) -> None:
        if not self.wait_for_backend():
            logger.error("Backend non raggiungibile su %s", self.base_url)
            sys.exit(1)
        try:
            import webview  # noqa: F401

            self.run_pywebview()
        except ImportError:
            logger.error("Installa dipendenze: pip install -r requirements.txt")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="JANIS desktop shell")
    parser.add_argument("--window", action="store_true", help="IDE completa 1280x820")
    parser.add_argument("--widget", action="store_true", help="Chat widget compatto")
    parser.add_argument("--overlay", action="store_true", help="Overlay fullscreen")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL backend JANIS")
    args = parser.parse_args()
    widget = not args.window and not args.overlay
    if args.widget:
        widget = True
    JanisDesktop(
        base_url=args.url,
        window_mode=args.window,
        widget_mode=widget,
        overlay_mode=args.overlay,
    ).run()


if __name__ == "__main__":
    main()
