"""Bridge MCP — manifest servers.json + alias locali + client stdio reale."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.MCP")

DEFAULT_MCP_SERVERS: list[dict] = [
    {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "enabled": False,
        "note": "Abilita se serve filesystem MCP esterno",
    },
    {
        "name": "codebase-memory",
        "command": "codebase-memory-mcp",
        "args": [],
        "enabled": True,
        "note": "DeusData — installare binario (W6b)",
    },
    {
        "name": "docling",
        "command": "docling-mcp-server",
        "args": [],
        "enabled": True,
        "note": "Docling — PDF/Office read (W6f); alias docling-mcp",
    },
    {
        "name": "officecli",
        "command": "officecli",
        "args": ["mcp"],
        "enabled": True,
        "note": "OfficeCLI — docx/xlsx/pptx edit (W6f)",
    },
    {
        "name": "vision",
        "command": "vision-mcp",
        "args": [],
        "enabled": True,
        "note": "vision-mcp OCR/video (W6i) — fallback Ollama describe_vision",
    },
    {
        "name": "research",
        "command": "ii-researcher-mcp",
        "args": [],
        "enabled": True,
        "note": "ii-researcher deep search (W6h)",
    },
    {
        "name": "mobile",
        "command": "mobile-mcp",
        "args": [],
        "enabled": True,
        "note": "mobile-mcp UI automation — tipicamente su Mac (W6j)",
    },
]


def _manifest_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "mcp" / "servers.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_mcp_servers() -> list[dict]:
    path = _manifest_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                by_name = {
                    (s.get("name") or "").strip(): s
                    for s in data
                    if isinstance(s, dict) and (s.get("name") or "").strip()
                }
                changed = False
                for d in DEFAULT_MCP_SERVERS:
                    name = (d.get("name") or "").strip()
                    if name and name not in by_name:
                        data.append(d)
                        changed = True
                if changed:
                    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                return data
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(DEFAULT_MCP_SERVERS, indent=2, ensure_ascii=False), encoding="utf-8")
    return list(DEFAULT_MCP_SERVERS)


async def mcp_tool_to_janis(tool_name: str, arguments: dict) -> str:
    """Mappa chiamata MCP-like su tool registry JANIS (fallback locale)."""
    from backend.core.tools.registry import execute_tool, list_tools

    alias = {
        "read_file": "read_file",
        "write_file": "write_file",
        "list_dir": "list_dir",
        "terminal": "terminal",
        "browser": "open_browser",
        "remember": "remember",
        "recall": "recall",
        "semantic_recall": "semantic_recall",
    }
    janis_tool = alias.get(tool_name, tool_name)
    if janis_tool not in list_tools():
        return f"Tool MCP '{tool_name}' non mappato. Disponibili: {', '.join(list_tools()[:15])}..."
    result = await execute_tool(janis_tool, arguments or {})
    return str(result)


async def list_mcp_capabilities() -> dict[str, Any]:
    servers = load_mcp_servers()
    from backend.core.tools.registry import list_tools

    status: list[dict] = []
    try:
        from backend.core.mcp_client import mcp_enabled, mcp_server_status

        if mcp_enabled():
            status = await mcp_server_status()
    except Exception as e:
        logger.warning("mcp_server_status: %s", e)

    return {
        "mcp_enabled": bool(getattr(settings, "MCP_ENABLED", True)),
        "mcp_servers": servers,
        "runtime_status": status,
        "janis_tools": list_tools(),
        "bridge": "mcp_call → remote stdio | fallback mcp_tool_to_janis",
    }
