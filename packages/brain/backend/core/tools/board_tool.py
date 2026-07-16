"""Tool orchestrator — board / ticket / heartbeat (pattern Paperclip)."""
from __future__ import annotations

import json

from backend.core.tools.registry import register


@register("board_status")
async def board_status_tool(_args: dict) -> str:
    from backend.core.orchestrator.board import board_status

    return json.dumps(board_status(), ensure_ascii=False, indent=2)


@register("ticket_create")
async def ticket_create(args: dict) -> str:
    from backend.core.orchestrator.board import create_ticket

    title = (args.get("title") or args.get("text") or "").strip()
    if not title:
        return "title obbligatorio"
    t = create_ticket(
        title,
        goal_id=args.get("goal_id"),
        assignee=args.get("assignee") or "brain-local",
        priority=int(args.get("priority") or 5),
        kind=args.get("kind") or "safe",
        detail=args.get("detail") or "",
    )
    return json.dumps(t, ensure_ascii=False, indent=2)


@register("ticket_claim")
async def ticket_claim(args: dict) -> str:
    from backend.core.orchestrator.board import claim_ticket

    agent = args.get("agent_id") or args.get("assignee") or "brain-local"
    tid = (args.get("ticket_id") or args.get("id") or "").strip() or None
    t = claim_ticket(agent, ticket_id=tid)
    if not t:
        return "Nessun ticket open claimabile"
    return json.dumps(t, ensure_ascii=False, indent=2)


@register("approvals_status")
async def approvals_status(_args: dict) -> str:
    from backend.core.approval import status as approval_status

    return json.dumps(approval_status(), ensure_ascii=False, indent=2)


@register("approval_decide")
async def approval_decide(args: dict) -> str:
    from backend.core.approval import decide_approval

    aid = (args.get("approval_id") or args.get("id") or "").strip()
    if not aid:
        return "approval_id obbligatorio"
    approve = args.get("approve", True)
    if isinstance(approve, str):
        approve = approve.lower() not in ("0", "false", "no", "reject")
    a = decide_approval(aid, approve=bool(approve), note=args.get("note") or "")
    if not a:
        return f"Approval {aid} non trovata"
    return json.dumps(a, ensure_ascii=False, indent=2)


@register("ticket_done")
async def ticket_done(args: dict) -> str:
    from backend.core.orchestrator.board import complete_ticket

    tid = (args.get("ticket_id") or args.get("id") or "").strip()
    if not tid:
        return "ticket_id obbligatorio"
    status = args.get("status") or "done"
    t = complete_ticket(tid, args.get("result") or "", status=status)
    if not t:
        return f"Ticket {tid} non trovato"
    return json.dumps(t, ensure_ascii=False, indent=2)


@register("agent_pause")
async def agent_pause(args: dict) -> str:
    from backend.core.orchestrator.board import pause_agent

    aid = (args.get("agent_id") or args.get("id") or "").strip()
    if not aid:
        return "agent_id obbligatorio"
    paused = args.get("paused", True)
    if isinstance(paused, str):
        paused = paused.lower() not in ("0", "false", "no", "resume")
    a = pause_agent(aid, bool(paused))
    if not a:
        return f"Agent {aid} non trovato"
    return json.dumps(a, ensure_ascii=False, indent=2)


@register("heartbeat_run")
async def heartbeat_run(args: dict) -> str:
    from backend.core.orchestrator.board import run_heartbeat

    agent = args.get("agent_id") or "brain-local"
    result = await run_heartbeat(agent)
    return json.dumps(result, ensure_ascii=False, indent=2)
