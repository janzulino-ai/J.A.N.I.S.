"""Test verify_mode_a script structure."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_verify_mode_a_doctor_ok(monkeypatch):
    from scripts import verify_mode_a

    async def fake_get(path: str):
        if path == "/api/status":
            return {"service": "JANIS"}
        if path == "/api/doctor":
            return {
                "summary": "giallo",
                "required_fail": [],
                "optional_fail": ["comfyui"],
                "fabric": {"summary": "amber", "counts": {"green": 2}},
            }
        if path.startswith("/api/capabilities"):
            return {"summary": "amber", "wave": 1, "capabilities": []}
        if path.startswith("/api/media"):
            return {"ok": True, "images": []}
        return None

    monkeypatch.setattr(verify_mode_a, "_http_get", fake_get)
    with patch.object(verify_mode_a, "_run_tools", AsyncMock(return_value={"mcp_status": "ok"})):
        code = await verify_mode_a.main()
    assert code == 0


@pytest.mark.asyncio
async def test_verify_mode_a_doctor_red(monkeypatch):
    from scripts import verify_mode_a

    async def fake_get(path: str):
        if path == "/api/status":
            return {"service": "JANIS"}
        if path == "/api/doctor":
            return {"summary": "rosso", "required_fail": ["ollama"], "optional_fail": []}
        return None

    monkeypatch.setattr(verify_mode_a, "_http_get", fake_get)
    with patch.object(verify_mode_a, "_run_tools", AsyncMock(return_value={})):
        code = await verify_mode_a.main()
    assert code == 2
