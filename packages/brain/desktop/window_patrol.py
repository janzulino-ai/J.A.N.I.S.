"""
Sposta la finestra JANIS sui bordi dello schermo (su/giù, destra/sinistra).
"""

from __future__ import annotations

import ctypes
import logging
import os
import time

logger = logging.getLogger("JANIS.Patrol")

SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010


def _screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def _find_hwnd(pid: int, title_hint: str) -> int | None:
    from desktop.wallpaper import find_hwnd_by_pid

    return find_hwnd_by_pid(pid, title_hint)


class WindowPatrol:
    """Muove la finestra widget verticalmente sul bordo destro/sinistro."""

    def __init__(
        self,
        pid: int,
        title: str,
        width: int,
        height: int,
        *,
        speed: float = 55.0,
    ):
        self.pid = pid
        self.title = title
        self.width = width
        self.height = height
        self.speed = speed
        self.edge = "right"
        self.y = float(height)
        self.direction = 1
        self._hwnd: int | None = None
        self._bounce_count = 0
        self._running = True

    def stop(self) -> None:
        self._running = False

    def _resolve_hwnd(self) -> int | None:
        if self._hwnd:
            try:
                import win32gui

                if win32gui.IsWindow(self._hwnd):
                    return self._hwnd
            except Exception:
                pass
        self._hwnd = _find_hwnd(self.pid, self.title)
        return self._hwnd

    def tick(self, dt: float) -> None:
        hwnd = self._resolve_hwnd()
        if not hwnd:
            return

        sw, sh = _screen_size()
        margin = 32
        max_y = max(margin, sh - self.height - margin)

        self.y += self.direction * self.speed * dt
        if self.y >= max_y:
            self.y = max_y
            self.direction = -1
            self._on_bounce()
        elif self.y <= margin:
            self.y = margin
            self.direction = 1
            self._on_bounce()

        x = sw - self.width - 12 if self.edge == "right" else 12

        try:
            import win32gui

            win32gui.SetWindowPos(
                hwnd, None, int(x), int(self.y),
                0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
            )
        except Exception as e:
            logger.debug("SetWindowPos: %s", e)

    def _on_bounce(self) -> None:
        self._bounce_count += 1
        if self._bounce_count >= 4:
            self._bounce_count = 0
            self.edge = "left" if self.edge == "right" else "right"

    def run_loop(self, interval: float = 0.033) -> None:
        last = time.time()
        while self._running:
            now = time.time()
            dt = min(0.1, now - last)
            last = now
            self.tick(dt)
            time.sleep(interval)


def start_window_patrol(
    title: str,
    width: int,
    height: int,
    *,
    pid: int | None = None,
) -> WindowPatrol:
    patrol = WindowPatrol(pid or os.getpid(), title, width, height)
    import threading

    threading.Thread(target=patrol.run_loop, daemon=True).start()
    return patrol
