import asyncio
import platform
import shutil
from backend.core.tools.registry import register


@register("system_info")
async def system_info(_args: dict) -> str:
    lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Macchina: {platform.node()}",
        f"CPU: {platform.processor()}",
        f"Python: {platform.python_version()}",
        f"Arch: {platform.machine()}",
    ]

    # GPU NVIDIA via nvidia-smi se disponibile
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

    total, used, free = shutil.disk_usage("C:\\")
    lines.append(f"Disco C: {free // (1024**3)} GB liberi / {total // (1024**3)} GB totali")
    return "\n".join(lines)
