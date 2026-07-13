"""Controllo display Windows — dormienza quando presenza su mobile."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("JANIS.Power")


def set_monitor_power(on: bool) -> bool:
    """Spegni/accendi monitor (Windows). Ritorna True se applicato."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        # SC_MONITORPOWER: 1=low, 2=off
        param = -1 if on else 2
        user32.SendMessageW(0xFFFF, 0x0112, 0xF170, param)
        logger.info("Monitor power: %s", "on" if on else "off")
        return True
    except Exception as e:
        logger.warning("set_monitor_power failed: %s", e)
        return False
