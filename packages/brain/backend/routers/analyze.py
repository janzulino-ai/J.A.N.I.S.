"""API analisi e roadmap feature."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ResearchBody(BaseModel):
    topic: str
    references: list[str] = []
    urls: list[str] = []


class ImplementBody(BaseModel):
    research_id: str | None = None
    task_index: int = 0
    proposal_id: str | None = None
    restart: bool = False


@router.get("/api/analyze/inventory")
async def analyze_inventory():
    from backend.core.tech_analysis import janis_inventory, seed_baseline_research

    seed_baseline_research()
    return janis_inventory()


@router.get("/api/analyze/roadmap")
async def analyze_roadmap():
    from backend.core.tech_analysis import build_roadmap, seed_baseline_research

    seed_baseline_research()
    return {"items": build_roadmap()}


@router.get("/api/analyze/research")
async def analyze_list():
    from backend.core.tech_analysis import list_research

    return {"items": list_research()}


@router.post("/api/analyze/research")
async def analyze_research(body: ResearchBody):
    from backend.core.tech_analysis import run_research

    return await run_research(body.topic, references=body.references, urls=body.urls)


@router.post("/api/analyze/implement")
async def analyze_implement(body: ImplementBody):
    from backend.core.tech_analysis import implement_roadmap_item

    return await implement_roadmap_item(
        research_id=body.research_id,
        task_index=body.task_index,
        proposal_id=body.proposal_id,
        restart=body.restart,
    )
