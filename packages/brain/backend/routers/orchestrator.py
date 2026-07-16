"""API orchestrator — board, autonomy, heartbeat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.orchestrator import board as board_mod

router = APIRouter(tags=["orchestrator"])


class TicketCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    detail: str = ""
    goal_id: str | None = None
    assignee: str = "brain-local"
    priority: int = 5
    kind: str = "safe"


class TicketDoneBody(BaseModel):
    result: str = ""
    status: str = "done"


class AutonomyBody(BaseModel):
    level: str = Field(description="L0|L1|L2|L3")


class AgentPauseBody(BaseModel):
    paused: bool = True


@router.get("/api/orchestrator/status")
async def orch_status():
    return {"ok": True, **board_mod.board_status()}


@router.get("/api/orchestrator/tickets")
async def orch_tickets(status: str | None = None):
    tickets = board_mod.load_tickets()
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    return {"ok": True, "tickets": list(reversed(tickets))[:100]}


@router.post("/api/orchestrator/tickets")
async def orch_create_ticket(body: TicketCreateBody):
    t = board_mod.create_ticket(
        body.title,
        goal_id=body.goal_id,
        assignee=body.assignee,
        priority=body.priority,
        kind=body.kind,
        detail=body.detail,
    )
    return {"ok": True, "ticket": t}


@router.post("/api/orchestrator/tickets/{ticket_id}/claim")
async def orch_claim(ticket_id: str, agent_id: str = "brain-local"):
    t = board_mod.get_ticket(ticket_id)
    if not t:
        raise HTTPException(404, "ticket non trovato")
    if t.get("status") != "open":
        raise HTTPException(400, f"status={t.get('status')}")
    claimed = board_mod.claim_ticket(agent_id, ticket_id=ticket_id)
    if not claimed:
        raise HTTPException(400, "claim fallito (agente in pausa?)")
    return {"ok": True, "ticket": claimed}


@router.post("/api/orchestrator/tickets/{ticket_id}/done")
async def orch_done(ticket_id: str, body: TicketDoneBody):
    t = board_mod.complete_ticket(ticket_id, body.result, status=body.status)
    if not t:
        raise HTTPException(404, "ticket non trovato")
    return {"ok": True, "ticket": t}


@router.post("/api/orchestrator/heartbeat")
async def orch_heartbeat(agent_id: str = "brain-local"):
    return await board_mod.run_heartbeat(agent_id)


@router.post("/api/orchestrator/autonomy")
async def orch_autonomy(body: AutonomyBody):
    try:
        g = board_mod.set_autonomy_level(body.level)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "autonomy_level": g.get("autonomy_level"), "mission": g.get("mission")}


@router.post("/api/orchestrator/agents/{agent_id}/pause")
async def orch_pause_agent(agent_id: str, body: AgentPauseBody):
    a = board_mod.pause_agent(agent_id, body.paused)
    if not a:
        raise HTTPException(404, "agent non trovato")
    return {"ok": True, "agent": a}


class ApprovalDecideBody(BaseModel):
    approve: bool = True
    note: str = ""


@router.get("/api/orchestrator/approvals")
async def orch_approvals():
    from backend.core.approval import status as approval_status

    return {"ok": True, **approval_status()}


@router.post("/api/orchestrator/approvals/{approval_id}/decide")
async def orch_decide_approval(approval_id: str, body: ApprovalDecideBody):
    from backend.core.approval import decide_approval

    a = decide_approval(approval_id, approve=body.approve, note=body.note)
    if not a:
        raise HTTPException(404, "approval non trovata")
    return {"ok": True, "approval": a}


@router.post("/api/orchestrator/notify")
async def orch_notify(title: str = "JANIS", body: str = ""):
    from backend.core.pocket_notify import notify_all

    results = notify_all(title, body or "ping", {"type": "manual"})
    return {"ok": True, "results": results}
