"""Metriche host Linux per kiosk /server."""
from __future__ import annotations

import os
import platform
import time

from fastapi import APIRouter

router = APIRouter()

_start = time.time()


@router.get("/api/host/metrics")
async def host_metrics():
    cpu_pct = 0.0
    mem_pct = 0.0
    temp_c = None
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        temps = getattr(psutil, "sensors_temperatures", lambda: {})()
        if temps:
            for entries in temps.values():
                if entries:
                    temp_c = entries[0].current
                    break
    except Exception:
        pass

    gpu_pct = 0.0
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        parts = out.strip().split(",")
        if parts:
            gpu_pct = float(parts[0].strip())
            if temp_c is None and len(parts) > 1:
                temp_c = float(parts[1].strip())
    except Exception:
        pass

    return {
        "hostname": platform.node(),
        "uptime_sec": int(time.time() - _start),
        "cpu": {"usage_pct": cpu_pct, "temp_c": temp_c},
        "memory": {"usage_pct": mem_pct},
        "gpu": {"usage_pct": gpu_pct},
        "platform": platform.system(),
    }


@router.get("/api/host/hardware")
async def host_hardware():
    import platform
    return {
        "summary": f"{platform.processor() or platform.machine()} · {platform.system()}",
        "cpu": {"model": platform.processor(), "arch": platform.machine()},
        "ram_gb": _ram_gb(),
    }


def _ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return None
