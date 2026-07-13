"""API auto-riflessione JANIS."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.reflect import (
    decide_proposal,
    list_proposals,
    run_reflection,
)

router = APIRouter()


class ReflectRunBody(BaseModel):
    dry_run: bool = False
    max_msgs: int = 60


class ProposalDecisionBody(BaseModel):
    accept: bool = True


@router.post("/api/reflect/run")
async def reflect_run(body: ReflectRunBody):
    return await run_reflection(dry_run=body.dry_run, max_msgs=body.max_msgs)


@router.get("/api/reflect/proposals")
async def reflect_proposals(status: str | None = "open"):
    return {"proposals": list_proposals(status=status)}


@router.post("/api/reflect/proposals/{proposal_id}/decision")
async def reflect_decide(proposal_id: str, body: ProposalDecisionBody):
    decided = decide_proposal(proposal_id, accept=body.accept)
    if not decided:
        return {"ok": False, "error": "Proposta non trovata"}
    return {"ok": True, "proposal": decided}


class AutodevBody(BaseModel):
    proposal_id: str | None = None
    task: str | None = None
    files: list[str] = []
    verify: bool = True
    restart: bool = False


@router.post("/api/autodev/run")
async def autodev_run(body: AutodevBody):
    from backend.core.autodev import autocode, autocode_proposal

    if body.proposal_id:
        return await autocode_proposal(body.proposal_id, restart=body.restart)
    if not body.task:
        return {"ok": False, "error": "Serve task o proposal_id"}
    return await autocode(body.task, files=body.files, verify=body.verify, restart=body.restart)
