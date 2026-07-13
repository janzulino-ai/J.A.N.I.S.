"""
Layer sfondo desktop Windows — stessa tecnica di Wallpaper Engine:
Progman/WorkerW + WebView2/WebGL + click-through.

Nessuna dipendenza da Wallpaper Engine (Steam).
"""

from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes

logger = logging.getLogger("JANIS.Wallpaper")

user32 = ctypes.windll.user32

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HWND_BOTTOM = 1


def _get_screen_size() -> tuple[int, int]:
    try:
        import webview

        screen = webview.screens[0] if webview.screens else None
        if screen:
            return int(screen.width), int(screen.height)
    except Exception:
        pass
    return (
        int(user32.GetSystemMetrics(0)),
        int(user32.GetSystemMetrics(1)),
    )


def find_workerw() -> int:
    """WorkerW dietro le icone (tecnica Progman 0x052C — usata anche da Wallpaper Engine)."""
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        raise RuntimeError("Progman non trovato")

    result = ctypes.c_ulong()
    user32.SendMessageTimeoutW(
        progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(result),
    )

    target = ctypes.c_ulong(0)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_with_shell(hwnd, _lparam):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found = user32.FindWindowExW(None, hwnd, "WorkerW", None)
            if found:
                target.value = found
        return True

    user32.EnumWindows(enum_with_shell, 0)
    if target.value:
        return int(target.value)

    fallback = ctypes.c_ulong(0)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_empty_workerw(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value != "WorkerW":
            return True
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            return True
        fallback.value = hwnd
        return False

    user32.EnumWindows(enum_empty_workerw, 0)
    if fallback.value:
        return int(fallback.value)

    logger.warning("WorkerW assente — fallback Progman")
    return int(progman)


def find_hwnd_by_pid(pid: int, title_hint: str = "") -> int | None:
    """Trova HWND top-level del processo wallpaper (WebView2 / pywebview)."""
    try:
        import win32gui
        import win32process
    except ImportError:
        return _find_hwnd_by_title(title_hint) if title_hint else None

    candidates: list[tuple[int, int, str, str]] = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if window_pid != pid:
            return True
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if cls in ("Shell_TrayWnd", "Program Manager", "DummyDWMListenerWindow"):
            return True
        rect = win32gui.GetWindowRect(hwnd)
        area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
        if area < 8000:
            return True
        score = area
        if title_hint and title_hint in title:
            score += 10_000_000
        if "Chrome_WidgetWin" in cls:
            score += 500_000
        candidates.append((score, int(hwnd), title, cls))
        return True

    win32gui.EnumWindows(callback, None)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _find_hwnd_by_title(title: str) -> int | None:
    hwnd = user32.FindWindowW(None, title)
    return int(hwnd) if hwnd else None


def _apply_child_style(hwnd: int) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style = (style | WS_CHILD | WS_VISIBLE) & ~WS_POPUP
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)

    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)


def set_click_through(hwnd: int, enabled: bool = True) -> None:
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enabled:
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    else:
        ex &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)


def embed_desktop_layer(hwnd: int, width: int | None = None, height: int | None = None) -> bool:
    """Incorpora HWND nel desktop sotto le icone."""
    if width is None or height is None:
        width, height = _get_screen_size()

    try:
        parent = find_workerw()
    except RuntimeError as e:
        logger.error("%s", e)
        return False

    _apply_child_style(hwnd)
    user32.SetParent(hwnd, parent)
    user32.SetWindowPos(
        hwnd,
        HWND_BOTTOM,
        0,
        0,
        width,
        height,
        SWP_SHOWWINDOW | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )
    set_click_through(hwnd, True)
    logger.info("Layer desktop attivo — hwnd=%s parent=%s (%dx%d)", hwnd, parent, width, height)
    return True


def attach_wallpaper_process(
    pid: int,
    title_hint: str,
    width: int | None = None,
    height: int | None = None,
) -> int | None:
    hwnd = find_hwnd_by_pid(pid, title_hint)
    if not hwnd:
        hwnd = _find_hwnd_by_title(title_hint)
    if not hwnd:
        return None
    if embed_desktop_layer(hwnd, width, height):
        return hwnd
    return None
