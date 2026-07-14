"""API workspace evolve — cartelle scrivibili da JANIS."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.evolve_paths import (
    ensure_workspace_dirs,
    evolve_dir,
    list_workspace,
    monorepo_root,
    safe_write,
)

router = APIRouter()


class EvolveWrite(BaseModel):
    path: str = Field(min_length=1, description="Relativo a workspaces/")
    content: str = ""


@router.get("/api/evolve/paths")
async def api_evolve_paths():
    paths = ensure_workspace_dirs()
    return {
        "monorepo": str(monorepo_root()),
        "workspaces": paths,
    }


@router.get("/api/evolve/files")
async def api_evolve_files():
    return {"files": list_workspace()}


@router.post("/api/evolve/write")
async def api_evolve_write(body: EvolveWrite):
    try:
        target = safe_write(body.path, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "path": str(target.relative_to(evolve_dir().parent))}
