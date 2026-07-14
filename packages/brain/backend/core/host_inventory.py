"""Inventario hardware host — probe live Linux."""
from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=timeout).strip()
    except Exception:
        return ""


def probe_host() -> dict:
    import psutil

    cpu_model = platform.processor() or _run(["bash", "-lc", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"]).strip()
    cpu_count = psutil.cpu_count(logical=True)
    mem = psutil.virtual_memory()

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(u.total / (1024 ** 3), 1),
                "free_gb": round(u.free / (1024 ** 3), 1),
                "used_pct": round(u.percent, 1),
            })
        except PermissionError:
            continue

    block = []
    for line in _run(["lsblk", "-dn", "-o", "NAME,SIZE,TYPE,MODEL"]).splitlines():
        parts = line.split(None, 3)
        if len(parts) >= 3:
            block.append({"name": parts[0], "size": parts[1], "type": parts[2], "model": parts[3] if len(parts) > 3 else ""})

    nics = []
    for name, addrs in psutil.net_if_addrs().items():
        if name == "lo":
            continue
        nics.append({
            "name": name,
            "addresses": [a.address for a in addrs if a.family.name in ("AF_INET", "AF_INET6")][:4],
        })

    gpu = []
    smi = _run([
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version,uuid",
        "--format=csv,noheader",
    ])
    for line in smi.splitlines():
        if line.strip():
            p = [x.strip() for x in line.split(",")]
            gpu.append({"name": p[0] if p else "", "vram": p[1] if len(p) > 1 else "", "driver": p[2] if len(p) > 2 else ""})

    usb_count = len(_run(["lsusb"]).splitlines()) if _run(["which", "lsusb"]) else 0

    inv = {
        "hostname": platform.node(),
        "platform": platform.system(),
        "release": platform.release(),
        "arch": platform.machine(),
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "cpu": {"model": cpu_model, "cores_logical": cpu_count},
        "memory_gb": round(mem.total / (1024 ** 3), 1),
        "disks": disks,
        "block_devices": block,
        "network": nics,
        "gpu": gpu,
        "usb_devices": usb_count,
    }
    return inv


def save_inventory(inv: dict | None = None) -> Path:
    inv = inv or probe_host()
    path = Path(settings.JANIS_PROJECT_DIR) / "data" / "hardware_live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_inventory() -> dict:
    path = Path(settings.JANIS_PROJECT_DIR) / "data" / "hardware_live.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return probe_host()
