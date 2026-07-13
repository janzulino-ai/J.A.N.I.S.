"""Apre URL nel browser di sistema — affidabile su Windows anche da subprocess."""
from __future__ import annotations

import logging
import subprocess
import sys
import webbrowser

logger = logging.getLogger("JANIS.OpenUrl")


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ValueError("URL vuoto")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def open_system_url(raw: str) -> str:
    """Apre l'URL nel browser predefinito. Ritorna l'URL normalizzato."""
    url = normalize_url(raw)
    if sys.platform == "win32":
        try:
            import os

            os.startfile(url)  # noqa: S606 — browser di sistema su Windows
            logger.info("Browser di sistema: %s", url)
            return url
        except OSError:
            pass
        try:
            subprocess.Popen(  # noqa: S603
                ["cmd", "/c", "start", "", url],
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            logger.info("Browser (start): %s", url)
            return url
        except OSError as e:
            logger.warning("start fallito: %s", e)
    webbrowser.open(url)
    logger.info("Browser (webbrowser): %s", url)
    return url
