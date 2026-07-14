"""Coda job laboratorio LLM — stato persistente."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.llm_lab.paths import jobs_state_path, lab_runs_dir


def _load_jobs() -> list[dict]:
    p = jobs_state_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("jobs", [])
    except json.JSONDecodeError:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    jobs_state_path().write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_runs(limit: int = 20) -> list[dict]:
    jobs = _load_jobs()
    jobs.sort(key=lambda j: j.get("started_at") or "", reverse=True)
    return jobs[:limit]


def get_run(run_id: str) -> dict | None:
    for j in _load_jobs():
        if j.get("id") == run_id:
            return j
    return None


def create_run(*, dataset: str, base_model: str, config: dict | None = None) -> dict:
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = lab_runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    job: dict[str, Any] = {
        "id": run_id,
        "status": "pending",
        "stage": "queued",
        "dataset": dataset,
        "base_model": base_model,
        "config": config or {},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "run_dir": str(run_dir),
        "log_path": str(run_dir / "train.log"),
        "metrics": {},
        "error": None,
    }
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)
    return job


def update_run(run_id: str, **fields) -> dict | None:
    jobs = _load_jobs()
    for j in jobs:
        if j.get("id") == run_id:
            j.update(fields)
            _save_jobs(jobs)
            return j
    return None


def latest_run() -> dict | None:
    runs = list_runs(limit=1)
    return runs[0] if runs else None


def active_run() -> dict | None:
    for j in _load_jobs():
        if j.get("status") in ("pending", "running"):
            return j
    return None
