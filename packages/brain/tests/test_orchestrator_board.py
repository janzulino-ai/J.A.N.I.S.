"""Test board orchestrator — ticket claim/done, autonomia."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def orch_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("JANIS_PROJECT_DIR", str(tmp_path))
    from backend.config import settings

    monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", str(tmp_path))
    (tmp_path / "data" / "orchestrator").mkdir(parents=True)
    yield tmp_path


def test_create_claim_done(orch_tmp):
    from backend.core.orchestrator import board as b

    t = b.create_ticket("Smoke test board", kind="safe", priority=1)
    assert t["status"] == "open"
    claimed = b.claim_ticket("brain-local")
    assert claimed is not None
    assert claimed["status"] == "claimed"
    assert claimed["id"] == t["id"]
    done = b.complete_ticket(t["id"], "ok")
    assert done["status"] == "done"
    st = b.board_status()
    assert st["tickets"].get("done", 0) >= 1


def test_autonomy_level(orch_tmp):
    from backend.core.orchestrator import board as b

    b.set_autonomy_level("L2")
    assert b.get_autonomy_level() == "L2"
    with pytest.raises(ValueError):
        b.set_autonomy_level("L9")


def test_agent_budget_pause(orch_tmp):
    from backend.core.orchestrator import board as b

    agents = b.load_agents()
    for a in agents:
        if a["id"] == "cursor-code":
            a["daily_budget_usd"] = 0.1
            a["spent_today_usd"] = 0.0
            a["status"] = "active"
    b.save_agents(agents)
    assert b.agent_budget_ok("cursor-code", 0.05)
    b.record_agent_spend("cursor-code", 0.15)
    agents2 = {a["id"]: a for a in b.load_agents()}
    assert agents2["cursor-code"]["status"] == "paused"
    assert not b.agent_budget_ok("cursor-code", 0.01)


@pytest.mark.asyncio
async def test_l2_gates_code_kind(orch_tmp, monkeypatch):
    from backend.core.orchestrator import board as b

    b.set_autonomy_level("L2")
    t = b.create_ticket("Patch codice", kind="code", priority=1)

    async def fake_pm(*_a, **_k):
        return "should not run"

    monkeypatch.setattr("backend.core.brain.process_message", fake_pm)
    result = await b.run_heartbeat("brain-local")
    assert result.get("action") == "gated"
    t2 = b.get_ticket(t["id"])
    assert t2["status"] == "blocked"
