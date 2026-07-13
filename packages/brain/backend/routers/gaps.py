from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.capability_gaps import list_gaps, log_gap, resolve_gap, stats, get_gap

router = APIRouter()


class GapCreate(BaseModel):
    description: str = Field(min_length=3)
    context: str | None = None
    tool: str | None = None
    severity: str = "medium"
    proposed_fix: str | None = None


class GapResolve(BaseModel):
    resolution: str | None = None


@router.get("/api/gaps")
async def api_list_gaps(status: str | None = None):
    return {
        "stats": stats(),
        "gaps": list_gaps(status=status),
    }


@router.get("/api/gaps/{gap_id}")
async def api_get_gap(gap_id: str):
    gap = get_gap(gap_id)
    if not gap:
        raise HTTPException(status_code=404, detail="Gap non trovato")
    return gap


@router.post("/api/gaps")
async def api_create_gap(body: GapCreate):
    entry = log_gap(
        body.description,
        context=body.context,
        tool=body.tool,
        severity=body.severity,
        proposed_fix=body.proposed_fix,
    )
    return entry


@router.post("/api/gaps/{gap_id}/resolve")
async def api_resolve_gap(gap_id: str, body: GapResolve):
    gap = resolve_gap(gap_id, body.resolution)
    if not gap:
        raise HTTPException(status_code=404, detail="Gap non trovato")
    return gap
