"""
Processo dedicato al layer animato del desktop (WebGL + WorkerW).
Stessa tecnologia di Wallpaper Engine, integrato nativamente in JANIS.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] JANIS.Layer: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "layer.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from desktop.wallpaper import attach_wallpaper_process, _get_screen_size

logger = logging.getLogger("JANIS.Layer")
DEFAULT_URL = "http://127.0.0.1:8001"
LAYER_TITLE = "JANIS::DesktopLayer"
ATTACH_ATTEMPTS = 40
ATTACH_INTERVAL = 0.5


class WallpaperHost:
    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url.rstrip("/")
        self._window = None
        self._attached = False
        self._pid = os.getpid()

    def _page_url(self) -> str:
        return f"{self.base_url}/?mode=wallpaper"

    def _attach_loop(self) -> None:
        sw, sh = _get_screen_size()
        for attempt in range(ATTACH_ATTEMPTS):
            if self._attached:
                return
            hwnd = attach_wallpaper_process(self._pid, LAYER_TITLE, sw, sh)
            if hwnd:
                self._attached = True
                logger.info("Sfondo animato collegato al desktop (tentativo %d)", attempt + 1)
                return
            time.sleep(ATTACH_INTERVAL)
        logger.error(
            "Impossibile collegare il layer desktop dopo %d tentativi. "
            "Prova: riavvia Esplora risorse (taskkill /f /im explorer.exe && start explorer)",
            ATTACH_ATTEMPTS,
        )

    def run(self) -> None:
        import webview

        sw, sh = _get_screen_size()
        self._window = webview.create_window(
            LAYER_TITLE,
            self._page_url(),
            width=sw,
            height=sh,
            x=0,
            y=0,
            frameless=True,
            transparent=True,
            on_top=False,
            easy_drag=False,
            resizable=False,
            fullscreen=False,
            background_color="#010408",
        )

        def on_loaded():
            threading.Thread(target=self._attach_loop, daemon=True).start()
            try:
                self._window.evaluate_js("window.JANIS?.setDisplayMode?.('wallpaper')")
            except Exception:
                pass

        self._window.events.loaded += on_loaded
        logger.info("Avvio layer WebGL — %s", self._page_url())
        webview.start(gui="edgechromium", debug=False)


def main():
    parser = argparse.ArgumentParser(description="JANIS desktop layer (WorkerW + WebGL)")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    WallpaperHost(base_url=args.url).run()


if __name__ == "__main__":
    main()
