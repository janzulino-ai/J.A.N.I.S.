"""Promuove candidati verificati → research → reflect proposals."""
from __future__ import annotations

from backend.core.paid_capabilities import register_from_scout
from backend.core.tech_analysis import research_to_proposals, run_research
from backend.core.tech_scout.discover import list_candidates, save_candidate


async def promote_candidate(candidate_id: str) -> dict:
    cand = next((c for c in list_candidates() if c.get("id") == candidate_id), None)
    if not cand:
        return {"ok": False, "error": "Candidato non trovato"}
    status = cand.get("status")
    if status not in ("verified", "partial"):
        return {"ok": False, "error": f"Status {status} — serve verified o partial"}

    topic = f"Integrare {cand.get('name')} in JANIS ({cand.get('deployment')})"
    research = await run_research(
        topic,
        references=["janis"],
        urls=[cand.get("url")] if cand.get("url") else [],
    )
    if not research.get("ok"):
        return research

    rid = research["research"].get("id")
    proposals = research_to_proposals(rid) if rid else []

    if cand.get("deployment") == "cloud_only":
        register_from_scout(cand)

    cand["status"] = "integrated"
    save_candidate(cand)
    return {
        "ok": True,
        "research_id": rid,
        "proposals_created": len(proposals),
        "candidate": cand.get("name"),
    }
