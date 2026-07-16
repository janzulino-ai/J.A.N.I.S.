"""Tool MCP — client stdio reale + fallback alias JANIS."""
from __future__ import annotations

import json

from backend.core.mcp_bridge import list_mcp_capabilities, mcp_tool_to_janis
from backend.core.tools.registry import register


@register("mcp_call")
async def mcp_call(args: dict) -> str:
    """
    Chiama tool MCP remoto o alias locale.
    args: server (opz.), tool|name, args|arguments
    Se server assente: prova alias JANIS.
    """
    tool = (args.get("tool") or args.get("name") or "").strip()
    arguments = args.get("args") or args.get("arguments") or {}
    server = (args.get("server") or "").strip()
    if not tool:
        return "tool obbligatorio per mcp_call"

    if server:
        try:
            from backend.core.mcp_client import call_mcp_tool, mcp_enabled

            if not mcp_enabled():
                return "MCP_ENABLED=false — abilita in .env"
            return await call_mcp_tool(server, tool, arguments if isinstance(arguments, dict) else {})
        except FileNotFoundError as e:
            return f"MCP server '{server}' non avviabile (comando mancante): {e}"
        except Exception as e:
            return f"Errore MCP {server}/{tool}: {e}"

    return await mcp_tool_to_janis(tool, arguments if isinstance(arguments, dict) else {})


@register("mcp_status")
async def mcp_status(_args: dict) -> str:
    cap = await list_mcp_capabilities()
    lines = [
        f"MCP enabled: {cap.get('mcp_enabled')}",
        f"Bridge: {cap.get('bridge')}",
        "",
        "Server dichiarati:",
    ]
    by_name = {s.get("name"): s for s in (cap.get("runtime_status") or [])}
    for s in cap.get("mcp_servers") or []:
        name = s.get("name")
        rt = by_name.get(name) or {}
        found = "cmd✓" if rt.get("command_found") else "cmd✗"
        sess = "session✓" if rt.get("session_active") else "session○"
        tools = rt.get("tools") or []
        lines.append(f"- {name}: {found} {sess} tools={len(tools)}")
        if rt.get("error"):
            lines.append(f"  err: {rt['error']}")
        if tools:
            lines.append(f"  → {', '.join(tools[:12])}")
    lines.append(f"\nTool JANIS: {len(cap.get('janis_tools') or [])}")
    return "\n".join(lines)


@register("mcp_list_tools")
async def mcp_list_tools(args: dict) -> str:
    """Lista tool di un server MCP (avvia sessione se necessario)."""
    server = (args.get("server") or "").strip()
    if not server:
        return "server obbligatorio"
    try:
        from backend.core.mcp_client import get_session, mcp_enabled

        if not mcp_enabled():
            return "MCP_ENABLED=false"
        sess = await get_session(server)
        tools = await sess.list_tools(force=True)
        return json.dumps({"server": server, "tools": tools}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Errore list tools {server}: {e}"
