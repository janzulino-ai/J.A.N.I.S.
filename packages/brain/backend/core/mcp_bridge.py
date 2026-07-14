"""Bridge MCP → execute_tool JANIS (pattern Odysseus)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.MCP")

# Server MCP noti — manifest locale (estendibile da scout)
DEFAULT_MCP_SERVERS: list[dict] = [
    {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
    {"name": "git", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "."]},
    {"name": "fetch", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
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
                return data
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(DEFAULT_MCP_SERVERS, indent=2), encoding="utf-8")
    return list(DEFAULT_MCP_SERVERS)


async def mcp_tool_to_janis(tool_name: str, arguments: dict) -> str:
    """Mappa chiamata MCP-like su tool registry JANIS."""
    from backend.core.tools.registry import execute_tool, list_tools

    # Alias comuni MCP → tool JANIS
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
    return {
        "mcp_servers": servers,
        "janis_tools": list_tools(),
        "bridge": "mcp_tool_to_janis",
    }
