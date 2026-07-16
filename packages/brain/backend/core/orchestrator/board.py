"""Board Paperclip-style — goals, tickets, agents, heartbeat claim."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.Orchestrator.Board")

AUTONOMY_LEVELS = ("L0", "L1", "L2", "L3")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _orch_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "orchestrator"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(name: str, default: Any) -> Any:
    f = _orch_dir() / name
    if not f.exists():
        f.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(name: str, data: Any) -> None:
    (_orch_dir() / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_run(entry: dict) -> None:
    f = _orch_dir() / "heartbeat_runs.jsonl"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def default_agents() -> list[dict]:
    return [
        {
            "id": "brain-local",
            "role": "local_reasoner",
            "status": "active",
            "daily_budget_usd": 0.0,
            "spent_today_usd": 0.0,
            "note": "Ollama / tool locali — budget 0 = illimitato locale",
        },
        {
            "id": "cursor-code",
            "role": "code_agent",
            "status": "active",
            "daily_budget_usd": 1.0,
            "spent_today_usd": 0.0,
        },
        {
            "id": "mac-node",
            "role": "fleet_worker",
            "status": "active",
            "daily_budget_usd": 0.0,
            "spent_today_usd": 0.0,
        },
        {
            "id": "lab-auditor",
            "role": "quality",
            "status": "active",
            "daily_budget_usd": 0.5,
            "spent_today_usd": 0.0,
        },
    ]


def default_goals() -> dict:
    return {
        "mission": "JANIS hub locale: senso, creazione, ricerca, dispositivi — autonomia L2 bounded",
        "autonomy_level": "L2",
        "goals": [
            {
                "id": "g-integration",
                "title": "Integrare MCP + orchestrator W6",
                "status": "open",
                "priority": 1,
            }
        ],
    }


def load_agents() -> list[dict]:
    data = _read_json("agents.json", {"agents": default_agents()})
    if isinstance(data, list):
        return data
    agents = data.get("agents") or default_agents()
    return agents


def save_agents(agents: list[dict]) -> None:
    _write_json("agents.json", {"agents": agents, "updated_at": _now()})


def load_goals() -> dict:
    return _read_json("goals.json", default_goals())


def save_goals(data: dict) -> None:
    data["updated_at"] = _now()
    _write_json("goals.json", data)


def load_tickets() -> list[dict]:
    data = _read_json("tickets.json", {"tickets": []})
    if isinstance(data, list):
        return data
    return list(data.get("tickets") or [])


def save_tickets(tickets: list[dict]) -> None:
    _write_json("tickets.json", {"tickets": tickets[-500:], "updated_at": _now()})


def get_autonomy_level() -> str:
    g = load_goals()
    lvl = (g.get("autonomy_level") or "L2").upper()
    return lvl if lvl in AUTONOMY_LEVELS else "L2"


def set_autonomy_level(level: str) -> dict:
    lvl = level.strip().upper()
    if lvl not in AUTONOMY_LEVELS:
        raise ValueError(f"Livello non valido: {level}")
    g = load_goals()
    g["autonomy_level"] = lvl
    save_goals(g)
    return g


def create_ticket(
    title: str,
    *,
    goal_id: str | None = None,
    assignee: str = "brain-local",
    priority: int = 5,
    kind: str = "safe",
    detail: str = "",
) -> dict:
    tickets = load_tickets()
    t = {
        "id": str(uuid.uuid4())[:12],
        "title": title.strip(),
        "detail": (detail or "").strip(),
        "goal_id": goal_id,
        "assignee": assignee,
        "status": "open",
        "priority": int(priority),
        "kind": kind,  # safe | code | media | device | cloud
        "created_at": _now(),
        "updated_at": _now(),
        "audit": [{"ts": _now(), "event": "created"}],
    }
    tickets.append(t)
    save_tickets(tickets)
    return t


def get_ticket(ticket_id: str) -> dict | None:
    for t in load_tickets():
        if t.get("id") == ticket_id:
            return t
    return None


def _update_ticket(ticket_id: str, mutator) -> dict | None:
    tickets = load_tickets()
    for i, t in enumerate(tickets):
        if t.get("id") == ticket_id:
            mutator(t)
            t["updated_at"] = _now()
            tickets[i] = t
            save_tickets(tickets)
            return t
    return None


def _agent_can_claim(agent_id: str) -> bool:
    agents = {a["id"]: a for a in load_agents()}
    ag = agents.get(agent_id)
    return not (ag and ag.get("status") == "paused")


def claim_ticket(agent_id: str = "brain-local", ticket_id: str | None = None) -> dict | None:
    """Prende un ticket open (specifico o a priorità più alta) assegnabile all'agente."""
    if not _agent_can_claim(agent_id):
        return None
    tickets = load_tickets()
    if ticket_id:
        candidates = [t for t in tickets if t.get("id") == ticket_id and t.get("status") == "open"]
    else:
        candidates = [
            t
            for t in tickets
            if t.get("status") == "open"
            and (not t.get("assignee") or t.get("assignee") == agent_id or t.get("assignee") == "any")
        ]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (int(t.get("priority") or 99), t.get("created_at") or ""))
    tid = candidates[0]["id"]

    def mut(t: dict) -> None:
        t["status"] = "claimed"
        t["assignee"] = agent_id
        t.setdefault("audit", []).append({"ts": _now(), "event": "claimed", "agent": agent_id})

    return _update_ticket(tid, mut)


def complete_ticket(ticket_id: str, result: str = "", *, status: str = "done") -> dict | None:
    if status not in ("done", "blocked"):
        status = "done"

    def mut(t: dict) -> None:
        t["status"] = status
        t["result"] = (result or "")[:4000]
        t.setdefault("audit", []).append({"ts": _now(), "event": status, "result": (result or "")[:200]})

    t = _update_ticket(ticket_id, mut)
    if t:
        _append_run(
            {
                "ts": _now(),
                "ticket_id": ticket_id,
                "status": status,
                "assignee": t.get("assignee"),
                "title": t.get("title"),
            }
        )
    return t


def pause_agent(agent_id: str, paused: bool = True) -> dict | None:
    agents = load_agents()
    for a in agents:
        if a.get("id") == agent_id:
            a["status"] = "paused" if paused else "active"
            a["updated_at"] = _now()
            save_agents(agents)
            return a
    return None


def agent_budget_ok(agent_id: str, estimate_usd: float = 0.01) -> bool:
    for a in load_agents():
        if a.get("id") != agent_id:
            continue
        if a.get("status") == "paused":
            return False
        budget = float(a.get("daily_budget_usd") or 0)
        if budget <= 0:
            return True  # 0 = illimitato per locale
        spent = float(a.get("spent_today_usd") or 0)
        return (spent + estimate_usd) <= budget
    return True


def record_agent_spend(agent_id: str, usd: float) -> None:
    agents = load_agents()
    today = datetime.now(timezone.utc).date().isoformat()
    for a in agents:
        if a.get("id") != agent_id:
            continue
        if a.get("spend_date") != today:
            a["spend_date"] = today
            a["spent_today_usd"] = 0.0
        a["spent_today_usd"] = float(a.get("spent_today_usd") or 0) + max(0.0, usd)
        budget = float(a.get("daily_budget_usd") or 0)
        if budget > 0 and a["spent_today_usd"] >= budget:
            a["status"] = "paused"
            logger.warning("Agent %s paused — budget esaurito", agent_id)
        save_agents(agents)
        return


def board_status() -> dict:
    tickets = load_tickets()
    by_status: dict[str, int] = {}
    for t in tickets:
        s = t.get("status") or "?"
        by_status[s] = by_status.get(s, 0) + 1
    goals = load_goals()
    return {
        "mission": goals.get("mission"),
        "autonomy_level": get_autonomy_level(),
        "goals_open": sum(1 for g in goals.get("goals") or [] if g.get("status") == "open"),
        "tickets": by_status,
        "tickets_total": len(tickets),
        "agents": [
            {
                "id": a.get("id"),
                "status": a.get("status"),
                "daily_budget_usd": a.get("daily_budget_usd"),
                "spent_today_usd": a.get("spent_today_usd"),
            }
            for a in load_agents()
        ],
        "open_tickets": [
            {"id": t["id"], "title": t.get("title"), "priority": t.get("priority"), "kind": t.get("kind")}
            for t in tickets
            if t.get("status") == "open"
        ][:20],
    }


async def run_heartbeat(agent_id: str = "brain-local") -> dict:
    """Claim + esegui un ticket safe via process_message (L1/L2)."""
    level = get_autonomy_level()
    if level == "L0":
        return {"ok": False, "reason": "autonomy L0 — solo assist"}

    ticket = claim_ticket(agent_id)
    if not ticket:
        return {"ok": True, "action": "idle", "reason": "nessun ticket open"}

    kind = (ticket.get("kind") or "safe").lower()
    # L1: solo propone già claimed → lascia done con nota
    if level == "L1":
        complete_ticket(ticket["id"], "L1: ticket proposto, esecuzione manuale richiesta", status="blocked")
        return {"ok": True, "action": "proposed", "ticket": ticket}

    # L2: solo kind safe (oppure ticket già approved)
    if level == "L2" and kind not in ("safe", "research", "index", "lab") and not ticket.get("approved"):
        complete_ticket(
            ticket["id"],
            f"L2: kind={kind} richiede approve (usa L3 o approva manualmente)",
            status="blocked",
        )
        try:
            from backend.core.approval import request_approval

            request_approval(
                ticket_id=ticket["id"],
                title=ticket.get("title") or "",
                kind=kind,
                reason=f"Autonomia L2: kind={kind} gated",
                agent_id=agent_id,
            )
        except Exception:
            logger.debug("approval request skip", exc_info=True)
        return {"ok": True, "action": "gated", "ticket": ticket, "kind": kind}

    if not agent_budget_ok(agent_id):
        complete_ticket(ticket["id"], "budget agente esaurito", status="blocked")
        return {"ok": False, "reason": "budget", "ticket": ticket}

    from backend.core.brain import process_message

    prompt = (
        f"[Heartbeat {agent_id}]\n"
        f"Esegui questo ticket e rispondi con il risultato operativo.\n"
        f"Titolo: {ticket.get('title')}\n"
        f"Dettaglio: {ticket.get('detail') or '(nessuno)'}\n"
        f"Kind: {kind}\n"
        f"Usa tool locali se possibile. Non spendere cloud senza necessità."
    )
    try:
        reply = await process_message(prompt, stream_final=False)
        complete_ticket(ticket["id"], reply or "ok", status="done")
        return {"ok": True, "action": "done", "ticket_id": ticket["id"], "reply": (reply or "")[:500]}
    except Exception as e:
        complete_ticket(ticket["id"], str(e), status="blocked")
        logger.exception("Heartbeat failed")
        return {"ok": False, "action": "error", "error": str(e), "ticket_id": ticket["id"]}
