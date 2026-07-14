"""Percorsi monorepo scrivibili da JANIS (auto-evoluzione)."""

from __future__ import annotations

import os
from pathlib import Path

from backend.config import settings

_BRAIN_ROOT = Path(__file__).resolve().parents[2]


def monorepo_root() -> Path:
    if settings.JANIS_MONOREPO_ROOT:
        return Path(settings.JANIS_MONOREPO_ROOT).expanduser().resolve()
    return _BRAIN_ROOT.parents[1]


def workspaces_root() -> Path:
    return monorepo_root() / "workspaces"


def evolve_dir() -> Path:
    return workspaces_root() / "evolve"


def sandbox_dir() -> Path:
    return workspaces_root() / "sandbox"


def runtime_dir() -> Path:
    return workspaces_root() / "runtime"


def ensure_workspace_dirs() -> dict[str, str]:
    """Crea cartelle evolve/sandbox/runtime se mancanti."""
    paths = {
        "evolve": evolve_dir(),
        "sandbox": sandbox_dir(),
        "runtime": runtime_dir(),
        "proposals": evolve_dir() / "proposals",
        "patches": evolve_dir() / "patches",
        "notes": evolve_dir() / "notes",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in paths.items()}


def safe_write(rel_path: str, content: str) -> Path:
    """Scrive solo sotto workspaces/."""
    root = workspaces_root().resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path fuori workspaces")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def list_workspace(max_depth: int = 3) -> list[dict]:
    root = workspaces_root()
    if not root.exists():
        return []
    items: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= max_depth:
            dirnames.clear()
            continue
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            items.append({
                "path": rel,
                "size": p.stat().st_size,
            })
    return items[:500]
