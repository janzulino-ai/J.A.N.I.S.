"""Verifica GPU NVIDIA per training Unsloth."""

from __future__ import annotations

import shutil
import subprocess


def gpu_status() -> dict:
    nv = shutil.which("nvidia-smi")
    if not nv:
        return {
            "available": False,
            "reason": "nvidia-smi non trovato",
            "gpus": [],
        }
    try:
        proc = subprocess.run(
            [
                nv,
                "--query-gpu=name,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return {
                "available": False,
                "reason": (proc.stderr or "nvidia-smi fallito").strip()[:200],
                "gpus": [],
            }
        gpus = []
        for line in proc.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append({
                    "name": parts[0],
                    "memory_total_mb": int(float(parts[1] or 0)),
                    "memory_free_mb": int(float(parts[2] or 0)),
                    "utilization_pct": int(float(parts[3] or 0)),
                })
        idle = all(g.get("utilization_pct", 100) < 30 for g in gpus) if gpus else False
        return {
            "available": bool(gpus),
            "idle": idle,
            "gpus": gpus,
            "count": len(gpus),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)[:200], "gpus": []}


def unsloth_venv_ready(python_path) -> dict:
    from pathlib import Path

    py = Path(python_path)
    if not py.exists():
        return {"ready": False, "reason": f"venv assente: {py}"}
    try:
        proc = subprocess.run(
            [str(py), "-c", "import unsloth; import torch; print(torch.cuda.is_available())"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        ok = proc.returncode == 0
        cuda = "True" in (proc.stdout or "")
        return {
            "ready": ok and cuda,
            "cuda": cuda,
            "import_ok": ok,
            "stderr": (proc.stderr or "")[:300] if not ok else None,
        }
    except Exception as e:
        return {"ready": False, "reason": str(e)[:200]}
