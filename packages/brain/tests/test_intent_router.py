"""Test intent router + doctor + approval."""
from __future__ import annotations

import pytest


def test_classify_research():
    from backend.core.intent_router import classify_intent

    h = classify_intent("Fammi una ricerca con fonti su MCP")
    assert h.intent == "research"
    assert "research" in h.tools


def test_classify_code():
    from backend.core.intent_router import classify_intent

    h = classify_intent("dove è definito il simbolo process_message nel codice")
    assert h.intent == "code"


def test_classify_doctor():
    from backend.core.intent_router import classify_intent

    h = classify_intent("janis doctor ora")
    assert h.intent == "doctor"


@pytest.mark.asyncio
async def test_doctor_runs():
    from backend.core.doctor import run_doctor

    report = await run_doctor(heal=False)
    assert "checks" in report
    assert report.get("summary") in ("verde", "giallo", "rosso")


def test_approval_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("JANIS_PROJECT_DIR", str(tmp_path))
    from backend.config import settings

    monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", str(tmp_path))
    from backend.core.approval import decide_approval, list_pending, request_approval
    from backend.core.orchestrator import board as b

    t = b.create_ticket("Risky patch", kind="code", priority=1)
    a = request_approval(ticket_id=t["id"], title=t["title"], kind="code", reason="test")
    assert a["status"] == "pending"
    assert list_pending()
    decided = decide_approval(a["id"], approve=True)
    assert decided["status"] == "approved"
    t2 = b.get_ticket(t["id"])
    assert t2["status"] == "open"
    assert t2.get("approved") is True
