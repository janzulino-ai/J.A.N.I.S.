"""API Tech Scout — discovery, test, verify, promote."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class DiscoverBody(BaseModel):
    topic: str = ""
    sources: list[str] = ["watchlist", "github"]


@router.get("/api/scout/candidates")
async def scout_candidates(status: str | None = None):
    from backend.core.tech_scout.discover import list_candidates
    return {"items": list_candidates(status=status)}


@router.post("/api/scout/discover")
async def scout_discover(body: DiscoverBody):
    from backend.core.tech_scout.discover import discover_all
    from backend.core.tech_scout.classifier import classify_candidate

    result = await discover_all(topic=body.topic, sources=body.sources)
    for c in result.get("candidates") or []:
        classify_candidate(c)
    return result


@router.post("/api/scout/test/{candidate_id}")
async def scout_test(candidate_id: str):
    from backend.core.tech_scout.sandbox import run_sandbox_test
    return await run_sandbox_test(candidate_id)


@router.get("/api/scout/report/{candidate_id}")
async def scout_report(candidate_id: str):
    from pathlib import Path
    from backend.config import settings
    import json

    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "scout" / "reports" / f"{candidate_id}.json"
    if not p.exists():
        return {"ok": False, "error": "Report non trovato"}
    return {"ok": True, "report": json.loads(p.read_text(encoding="utf-8"))}


@router.post("/api/scout/promote/{candidate_id}")
async def scout_promote(candidate_id: str):
    from backend.core.tech_scout.promote import promote_candidate
    return await promote_candidate(candidate_id)


@router.get("/api/scout/status")
async def scout_status():
    from backend.core.tech_scout.discover import list_candidates
    items = list_candidates()
    by_status: dict[str, int] = {}
    for c in items:
        s = c.get("status") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "total": len(items),
        "by_status": by_status,
        "recent": items[:5],
    }
