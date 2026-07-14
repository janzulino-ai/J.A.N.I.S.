"""Percorsi laboratorio LLM (data + workspaces)."""

from __future__ import annotations

from pathlib import Path

from backend.config import settings
from backend.core.evolve_paths import monorepo_root, workspaces_root

_BRAIN_ROOT = Path(__file__).resolve().parents[3]


def lab_data_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "lab"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lab_workspace() -> Path:
    return workspaces_root() / "lab"


def lab_datasets_dir() -> Path:
    p = lab_workspace() / "datasets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lab_runs_dir() -> Path:
    p = lab_workspace() / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lab_configs_dir() -> Path:
    p = lab_workspace() / "configs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lab_venv_python() -> Path:
    if settings.LAB_VENV_PATH:
        return Path(settings.LAB_VENV_PATH).expanduser() / "bin" / "python3"
    home = Path(settings.JANIS_WORKSPACE or "~").expanduser()
    return home / ".janis-lab-venv" / "bin" / "python3"


def lab_train_script() -> Path:
    root = monorepo_root()
    return root / "infra" / "lab" / "train_unsloth.py"


def jobs_state_path() -> Path:
    return lab_data_dir() / "jobs.json"


def curated_dataset_path() -> Path:
    return lab_datasets_dir() / "curated.jsonl"


def harvest_state_path() -> Path:
    return lab_data_dir() / "harvest_state.json"


def ensure_lab_dirs() -> dict[str, str]:
    paths = {
        "data": lab_data_dir(),
        "workspace": lab_workspace(),
        "datasets": lab_datasets_dir(),
        "runs": lab_runs_dir(),
        "configs": lab_configs_dir(),
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in paths.items()}
