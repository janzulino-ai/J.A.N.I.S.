import asyncio
import os
import platform
import shutil
from backend.core.tools.registry import register


def _primary_disk_path() -> str:
    if platform.system() == "Windows":
        return "C:\\"
    return os.path.expanduser("~")


@register("system_info")
async def system_info(_args: dict) -> str:
    lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Macchina: {platform.node()}",
        f"CPU: {platform.processor()}",
        f"Python: {platform.python_version()}",
        f"Arch: {platform.machine()}",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi", "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        gpu = out.decode("utf-8", errors="replace").strip()
        if gpu:
            lines.append(f"GPU: {gpu}")
    except Exception:
        pass

    try:
        import psutil
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                lines.append(
                    f"Disco {part.mountpoint}: {usage.free // (1024**3)} GB liberi / "
                    f"{usage.total // (1024**3)} GB totali ({usage.percent}% usato)"
                )
            except PermissionError:
                continue
    except Exception:
        disk_path = _primary_disk_path()
        total, used, free = shutil.disk_usage(disk_path)
        label = disk_path.rstrip("\\/")
        lines.append(f"Disco {label}: {free // (1024**3)} GB liberi / {total // (1024**3)} GB totali")

    return "\n".join(lines)
