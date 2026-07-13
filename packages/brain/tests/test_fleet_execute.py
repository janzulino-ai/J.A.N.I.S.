"""Test Fleet Fase 2 — command_result."""
from __future__ import annotations

import asyncio


def test_fleet_resolve_command():
    from backend.core.fleet.manager import MacBridgeManager

    mgr = MacBridgeManager()
    loop = asyncio.new_event_loop()
    fut = loop.create_future()
    mgr._pending_commands["t1"] = fut
    mgr.resolve_command("t1", {"ok": True, "stdout": "hello fleet"})
    result = loop.run_until_complete(fut)
    assert result["stdout"] == "hello fleet"
