"""Test MCP client — framing + fallback senza binario esterno."""
from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_mcp_call_local_fallback(monkeypatch):
    from backend.core.tools import mcp_tool

    async def fake_local(tool, arguments):
        return f"local:{tool}:{arguments.get('path', '')}"

    monkeypatch.setattr(mcp_tool, "mcp_tool_to_janis", fake_local)
    out = await mcp_tool.mcp_call({"tool": "read_file", "arguments": {"path": "x.txt"}})
    assert out.startswith("local:read_file:")


@pytest.mark.asyncio
async def test_mcp_disabled(monkeypatch):
    from backend.config import settings
    from backend.core.mcp_client import call_mcp_tool

    monkeypatch.setattr(settings, "MCP_ENABLED", False)
    with pytest.raises(RuntimeError, match="MCP_ENABLED"):
        await call_mcp_tool("codebase-memory", "search", {})


def test_content_length_roundtrip():
    """Verifica framing Content-Length usato dal client."""
    payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    data = json.dumps(payload).encode("utf-8")
    frame = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data
    sep = frame.find(b"\r\n\r\n")
    assert sep > 0
    header = frame[:sep].decode()
    length = int(header.split(":", 1)[1].strip())
    body = frame[sep + 4 : sep + 4 + length]
    assert json.loads(body)["id"] == 1
