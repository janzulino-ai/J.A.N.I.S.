"""Metriche host Linux per kiosk /server — psutil + Glances opzionale."""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import httpx
from fastapi import APIRouter

from backend.config import settings

router = APIRouter()

_boot = time.time()
_ring: list[dict] = []
_RING_MAX = 60


def _metrics_ring_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "metrics_ring.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_ring() -> list[dict]:
    global _ring
    if _ring:
        return _ring
    f = _metrics_ring_path()
    if f.exists():
        try:
            _ring = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _ring = []
    return _ring


def _save_ring() -> None:
    _metrics_ring_path().write_text(json.dumps(_ring[-_RING_MAX:], ensure_ascii=False), encoding="utf-8")


def _append_ring(snapshot: dict) -> None:
    global _ring
    _ring = _load_ring()
    _ring.append({"ts": int(time.time()), **snapshot})
    if len(_ring) > _RING_MAX:
        _ring = _ring[-_RING_MAX:]
    _save_ring()


async def _fetch_glances() -> dict | None:
    url = (settings.GLANCES_URL or "").rstrip("/")
    if not url:
        return None
    for path in ("/api/4/all", "/api/3/all"):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{url}{path}")
                if r.status_code == 200:
                    return r.json()
        except Exception:
            continue
    return None


def _psutil_metrics() -> dict:
    cpu_pct = 0.0
    mem_pct = 0.0
    temp_c = None
    disk = []
    net = {"rx_bytes": 0, "tx_bytes": 0}
    load_avg = None
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
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk.append({
                    "mount": part.mountpoint,
                    "total_gb": round(usage.total / (1024 ** 3), 1),
                    "used_pct": round(usage.percent, 1),
                    "free_gb": round(usage.free / (1024 ** 3), 1),
                })
            except PermissionError:
                continue
        nio = psutil.net_io_counters()
        if nio:
            net = {"rx_bytes": nio.bytes_recv, "tx_bytes": nio.bytes_sent}
        if hasattr(psutil, "getloadavg"):
            la = psutil.getloadavg()
            load_avg = {"1m": la[0], "5m": la[1], "15m": la[2]}
    except Exception:
        pass
    return {
        "cpu_pct": cpu_pct,
        "mem_pct": mem_pct,
        "temp_c": temp_c,
        "disk": disk,
        "net": net,
        "load_avg": load_avg,
    }


def _gpu_metrics() -> dict:
    gpu_pct = 0.0
    vram_mb = None
    temp_c = None
    name = None
    try:
        import subprocess
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        parts = [p.strip() for p in out.strip().split(",")]
        if len(parts) >= 4:
            name, gpu_pct, vram_mb, temp_c = parts[0], float(parts[1]), float(parts[2]), float(parts[3])
        elif parts:
            gpu_pct = float(parts[0])
    except Exception:
        pass
    return {"usage_pct": gpu_pct, "vram_mb": vram_mb, "temp_c": temp_c, "name": name}


@router.get("/api/host/metrics")
async def host_metrics():
    ps = _psutil_metrics()
    gpu = _gpu_metrics()
    glances = await _fetch_glances()

    if glances:
        try:
            ps["cpu_pct"] = glances.get("cpu", {}).get("total", ps["cpu_pct"])
            mem = glances.get("mem", {})
            if mem.get("percent") is not None:
                ps["mem_pct"] = mem["percent"]
        except Exception:
            pass

    snapshot = {
        "cpu": ps["cpu_pct"],
        "mem": ps["mem_pct"],
        "gpu": gpu.get("usage_pct", 0),
    }
    _append_ring(snapshot)

    try:
        import psutil
        boot_uptime = int(time.time() - psutil.boot_time())
    except Exception:
        boot_uptime = int(time.time() - _boot)

    return {
        "hostname": platform.node(),
        "uptime_sec": boot_uptime,
        "cpu": {"usage_pct": ps["cpu_pct"], "temp_c": ps["temp_c"], "load_avg": ps["load_avg"]},
        "memory": {"usage_pct": ps["mem_pct"]},
        "gpu": gpu,
        "disk": ps["disk"],
        "network": ps["net"],
        "platform": platform.system(),
        "glances": glances is not None,
        "history": _load_ring()[-30:],
        "process_uptime_sec": int(time.time() - _boot),
    }


@router.get("/api/host/hardware")
async def host_hardware():
    from backend.core.host_inventory import load_inventory
    live = load_inventory()
    return {
        "summary": f"{live.get('cpu', {}).get('model') or platform.processor() or platform.machine()} · {platform.system()}",
        "cpu": {"model": live.get("cpu", {}).get("model"), "arch": platform.machine(), "cores": live.get("cpu", {}).get("cores_logical")},
        "ram_gb": live.get("memory_gb") or _ram_gb(),
        "gpu": live.get("gpu") or [],
        "disks": live.get("disks") or [],
        "network": live.get("network") or [],
    }


@router.get("/api/host/inventory")
async def host_inventory(refresh: bool = False):
    from backend.core.host_inventory import load_inventory, probe_host, save_inventory
    if refresh:
        inv = probe_host()
        save_inventory(inv)
        return {"ok": True, "refreshed": True, "inventory": inv}
    return {"ok": True, "inventory": load_inventory()}


def _ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return None
