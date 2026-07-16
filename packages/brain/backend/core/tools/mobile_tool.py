"""Mobile UI automation — mobile-mcp su Mac via fleet/MCP (W6j)."""
from __future__ import annotations

import json

from backend.core.sidecar_call import call_mcp, missing_sidecar, pick_mcp_tool, run_cli
from backend.core.tools.registry import register


@register("mobile_ui")
async def mobile_ui(args: dict) -> str:
    """
    Automazione UI iOS/Android via mobile-mcp.
    args: action (tap|swipe|screenshot|launch|list), target|selector, device, text
    """
    action = (args.get("action") or "screenshot").strip().lower()
    target = (args.get("target") or args.get("selector") or args.get("app") or "").strip()
    text = (args.get("text") or "").strip()
    device = (args.get("device") or "").strip()

    try:
        from backend.core.mcp_client import get_session

        tools = await (await get_session("mobile")).list_tools()
        name = pick_mcp_tool(
            tools,
            action,
            f"mobile_{action}",
            "tap",
            "screenshot",
            "launch_app",
            "list_devices",
            "run",
        )
        if name:
            out = await call_mcp(
                "mobile",
                name,
                {
                    "action": action,
                    "target": target,
                    "selector": target,
                    "text": text,
                    "device": device,
                },
            )
            if out:
                return out
    except Exception:
        pass

    # Fleet Mac: prova comando mobile-mcp remoto
    try:
        from backend.core.fleet.manager import fleet_manager

        cmd = f"mobile-mcp {action}"
        if target:
            cmd += f" {target}"
        if text:
            cmd += f" --text {text!r}"
        result = await fleet_manager.execute_command("mac-node", cmd)
        if result.get("ok"):
            return (result.get("stdout") or json.dumps(result))[:8000]
    except Exception:
        pass

    code, out, err = await run_cli("mobile-mcp", [action, target] if target else [action], timeout=60)
    if code == 0:
        return out or "ok"
    return missing_sidecar(
        "mobile-mcp",
        "Installa mobile-mcp sul Mac Mini e registra server 'mobile' in servers.json; "
        "oppure usa fleet_execute su mac-node.",
    )


@register("mobile_status")
async def mobile_status(_args: dict) -> str:
    from backend.core.fleet.manager import fleet_manager
    from backend.core.mcp_client import mcp_server_status

    status = await mcp_server_status()
    mobile = next((s for s in status if s.get("name") == "mobile"), None)
    fleet = fleet_manager.fleet_status()
    return json.dumps(
        {"mcp_mobile": mobile, "fleet": fleet, "tool": "mobile_ui"},
        ensure_ascii=False,
        indent=2,
    )
