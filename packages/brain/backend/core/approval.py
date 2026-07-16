"""Approval gates — ticket rischiosi in coda approve + notify Pocket (W7a)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.Approval")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "orchestrator" / "approvals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_approvals() -> list[dict]:
    f = _path()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.get("items") or [])
        return []
    except Exception:
        return []


def save_approvals(items: list[dict]) -> None:
    _path().write_text(
        json.dumps({"items": items[-200:], "updated_at": _now()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def request_approval(
    *,
    ticket_id: str,
    title: str,
    kind: str,
    reason: str,
    agent_id: str = "brain-local",
) -> dict:
    items = load_approvals()
    for a in items:
        if a.get("ticket_id") == ticket_id and a.get("status") == "pending":
            return a
    entry = {
        "id": str(uuid.uuid4())[:12],
        "ticket_id": ticket_id,
        "title": title,
        "kind": kind,
        "reason": reason,
        "agent_id": agent_id,
        "status": "pending",
        "created_at": _now(),
        "decided_at": None,
    }
    items.append(entry)
    save_approvals(items)
    try:
        from backend.core.pocket_notify import notify_all

        notify_all(
            title="JANIS — approve richiesta",
            body=f"{kind}: {title}\n{reason[:160]}",
            data={"type": "approval", "approval_id": entry["id"], "ticket_id": ticket_id},
        )
    except Exception:
        logger.debug("notify approval skip", exc_info=True)
    return entry


def decide_approval(approval_id: str, *, approve: bool, note: str = "") -> dict | None:
    items = load_approvals()
    found = None
    for a in items:
        if a.get("id") == approval_id:
            a["status"] = "approved" if approve else "rejected"
            a["decided_at"] = _now()
            a["note"] = note
            found = a
            break
    if not found:
        return None
    save_approvals(items)

    # Sblocca ticket: approved → open per heartbeat L3/manual; rejected resta blocked
    try:
        from backend.core.orchestrator import board as board_mod

        tid = found.get("ticket_id")
        if approve and tid:

            def mut(t: dict) -> None:
                t["status"] = "open"
                t["kind"] = t.get("kind") or found.get("kind") or "code"
                t["approved"] = True
                t.setdefault("audit", []).append({"ts": _now(), "event": "approved", "approval_id": approval_id})

            board_mod._update_ticket(tid, mut)
        elif tid:

            def mut_r(t: dict) -> None:
                t["status"] = "blocked"
                t.setdefault("audit", []).append({"ts": _now(), "event": "rejected", "approval_id": approval_id})

            board_mod._update_ticket(tid, mut_r)
    except Exception:
        logger.exception("decide_approval ticket update")
    return found


def list_pending() -> list[dict]:
    return [a for a in load_approvals() if a.get("status") == "pending"]


def status() -> dict[str, Any]:
    items = load_approvals()
    by = {}
    for a in items:
        s = a.get("status") or "?"
        by[s] = by.get(s, 0) + 1
    return {"counts": by, "pending": list_pending()[:20]}
