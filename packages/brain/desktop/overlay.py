"""
Overlay fullscreen sopra il desktop Windows (topmost + click-through opzionale).
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

logger = logging.getLogger("JANIS.Overlay")

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010


def find_overlay_hwnd(pid: int, title_hint: str) -> int | None:
    from desktop.wallpaper import find_hwnd_by_pid

    return find_hwnd_by_pid(pid, title_hint)


def set_click_through(hwnd: int, enabled: bool) -> None:
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enabled:
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    else:
        ex &= ~WS_EX_TRANSPARENT
        ex |= WS_EX_LAYERED
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)


def hide_from_alt_tab(hwnd: int) -> None:
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW)


def set_topmost(hwnd: int) -> None:
    user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE,
    )


def configure_fullscreen_overlay(
    pid: int,
    title: str,
    *,
    click_through: bool = False,
    retries: int = 30,
    interval: float = 0.4,
) -> int | None:
    hwnd = None
    for _ in range(retries):
        hwnd = find_overlay_hwnd(pid, title)
        if hwnd:
            break
        time.sleep(interval)
    if not hwnd:
        logger.error("HWND overlay non trovato: %s", title)
        return None

    hide_from_alt_tab(hwnd)
    set_topmost(hwnd)
    set_click_through(hwnd, click_through)
    logger.info(
        "Overlay fullscreen attivo hwnd=%s click_through=%s",
        hwnd, click_through,
    )
    return hwnd
