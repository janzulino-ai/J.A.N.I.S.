"""Stato condiviso desktop overlay / screensaver."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

DisplayMode = Literal["browser", "overlay", "screensaver", "hidden", "wallpaper", "fullscreen"]


@dataclass
class DesktopState:
    mode: DisplayMode = "overlay"
    muted: bool = False
    idle_seconds: float = 0.0
    screensaver_threshold_sec: float = 300.0


_state = DesktopState()


def get_state() -> dict:
    return asdict(_state)


def set_mode(mode: DisplayMode) -> dict:
    _state.mode = mode
    return get_state()


def set_muted(muted: bool) -> dict:
    _state.muted = muted
    return get_state()


def update_idle(idle_seconds: float) -> dict:
    _state.idle_seconds = idle_seconds
    if (
        _state.mode == "overlay"
        and idle_seconds >= _state.screensaver_threshold_sec
    ):
        _state.mode = "screensaver"
    return get_state()
