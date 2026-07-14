"""Tool MCP bridge."""
from backend.core.mcp_bridge import list_mcp_capabilities, mcp_tool_to_janis
from backend.core.tools.registry import register


@register("mcp_call")
async def mcp_call(args: dict) -> str:
    tool = (args.get("tool") or args.get("name") or "").strip()
    arguments = args.get("args") or args.get("arguments") or {}
    if not tool:
        return "tool obbligatorio per mcp_call"
    return await mcp_tool_to_janis(tool, arguments)


@register("mcp_status")
async def mcp_status(_args: dict) -> str:
    cap = await list_mcp_capabilities()
    lines = ["MCP bridge JANIS:"]
    for s in cap.get("mcp_servers") or []:
        lines.append(f"- server: {s.get('name')} ({s.get('command')})")
    lines.append(f"Tool JANIS mappabili: {len(cap.get('janis_tools') or [])}")
    return "\n".join(lines)
