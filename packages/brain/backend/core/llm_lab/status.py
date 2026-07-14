"""Stato aggregato laboratorio LLM per API e HUD."""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings
from backend.core.llm_lab.gpu import gpu_status, unsloth_venv_ready
from backend.core.llm_lab.jobs import active_run, latest_run, list_runs
from backend.core.llm_lab.paths import (
    curated_dataset_path,
    ensure_lab_dirs,
    harvest_state_path,
    lab_datasets_dir,
    lab_venv_python,
)


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


async def lab_status() -> dict:
    ensure_lab_dirs()
    gpu = gpu_status()
    venv = unsloth_venv_ready(lab_venv_python())
    curated_n = _count_jsonl(curated_dataset_path())
    harvest_files = list(lab_datasets_dir().glob("harvest-*.jsonl"))

    harvest_state = {}
    if harvest_state_path().exists():
        try:
            harvest_state = json.loads(harvest_state_path().read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    active = active_run()
    latest = latest_run()
    runs = list_runs(limit=5)

    ready_train = (
        settings.LAB_ENABLED
        and curated_n >= settings.LAB_MIN_DATASET_SIZE
        and gpu.get("available")
        and venv.get("ready")
        and not active
    )

    return {
        "enabled": settings.LAB_ENABLED,
        "auto_train": settings.LAB_AUTO_TRAIN_ENABLED,
        "auto_promote": settings.LAB_AUTO_PROMOTE,
        "min_dataset_size": settings.LAB_MIN_DATASET_SIZE,
        "curated_examples": curated_n,
        "harvest_files": len(harvest_files),
        "last_harvest_at": harvest_state.get("last_harvest_at"),
        "base_model": settings.LAB_BASE_MODEL,
        "ollama_model_name": settings.LAB_OLLAMA_MODEL_NAME,
        "gpu": gpu,
        "venv": venv,
        "ready_train": ready_train,
        "active_run": active,
        "latest_run": latest,
        "recent_runs": runs,
        "setup_hint": "bash infra/lab/setup-unsloth.sh" if not venv.get("ready") else None,
    }
