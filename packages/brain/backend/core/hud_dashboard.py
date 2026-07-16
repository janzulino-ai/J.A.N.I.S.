"""Aggregazione dati HUD kiosk — una sola risposta con tutto ciò che il server rileva."""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path

from backend.config import settings


async def build_dashboard(*, refresh_inventory: bool = False) -> dict:
    from backend.core.host_inventory import load_inventory, probe_host, save_inventory
    from backend.core.tools.memory_tool import get_knowledge_stats
    from backend.core.tech_scout.discover import list_candidates
    from backend.core.capability_gaps import list_gaps, stats as gap_stats
    from backend.core.mcp_bridge import list_mcp_capabilities
    from backend.core.tools.registry import list_tools, list_active_tools
    from backend.core.scheduler import scheduler_status
    from backend.core import win_vm
    from backend.routers.host_metrics import _psutil_metrics, _gpu_metrics, _fetch_glances, _sidecar_health, _boot
    from backend.core.brain import check_ollama, get_session_history
    from backend.core.orchestrator.cost_router import cost_router
    from backend.core.runtime_config import get_runtime
    from backend.core.ssh_client import mac_ssh_ping
    from backend.core.fleet.manager import fleet_manager
    from backend.core import presence
    from backend.routers.stt import _probe_engines
    from backend.core.llm_usage import summary_today
    from backend.core.llm_router import get_active_provider
    from backend.core.paid_capabilities import list_capabilities
    from backend.core.channels.skills_manifest import channel_skill_status
    from backend.routers.websocket import manager

    if refresh_inventory:
        inv = probe_host()
        save_inventory(inv)
    else:
        inv = load_inventory()

    ps = _psutil_metrics()
    gpu = _gpu_metrics()
    glances = await _fetch_glances()
    if glances:
        try:
            ps["cpu_pct"] = glances.get("cpu", {}).get("total", ps["cpu_pct"])
            mem = glances.get("mem", {})
            if mem.get("percent") is not None:
                ps["mem_pct"] = mem["percent"]
        except Exception:
            pass

    sidecars = await _sidecar_health(glances is not None)
    ollama = await check_ollama()
    sidecars["ollama"] = bool(ollama.get("online"))

    rt = get_runtime()
    mac = await mac_ssh_ping()
    stt = _probe_engines()
    llm_prov = await get_active_provider()
    orch = cost_router.status()
    try:
        from backend.core.orchestrator.board import board_status

        orch = {**orch, "board": board_status()}
    except Exception:
        orch = {**orch, "board": None}
    usage = summary_today()
    skills = channel_skill_status()
    gaps_s = gap_stats()
    open_gaps = list_gaps(status="open")[:8]
    scout_items = list_candidates()
    by_status: dict[str, int] = {}
    for c in scout_items:
        s = c.get("status") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

    try:
        import psutil
        boot_uptime = int(time.time() - psutil.boot_time())
    except Exception:
        boot_uptime = int(time.time() - _boot)

    mcp = await list_mcp_capabilities()
    win = await win_vm.vm_status()
    sched = scheduler_status()

    from backend.core.perception import build_perception_status
    from backend.core.reflect import list_proposals
    from backend.core.ollama_model_router import get_probe_status
    from backend.core.evolve_paths import ensure_workspace_dirs
    from backend.core.llm_lab.status import lab_status

    perception = await build_perception_status()
    llm_probe = await get_probe_status()
    lab = await lab_status()
    proposals = list_proposals()
    open_proposals = [p for p in proposals if p.get("status") == "open"]
    evolve_paths = ensure_workspace_dirs()

    from backend.core.knowledge_graph import build_knowledge_graph

    kg = build_knowledge_graph(limit=48)
    kg_user = sum(1 for n in kg.get("nodes", []) if n.get("source") == "user")
    kg_janis = sum(1 for n in kg.get("nodes", []) if n.get("source") != "user")

    autonomy_state = {
        "enabled": settings.AUTONOMY_ENABLED,
        "reflect": settings.AUTONOMY_REFLECT_ENABLED,
        "autodev": settings.AUTONOMY_AUTODEV_ENABLED,
        "interval_min": settings.AUTONOMY_INTERVAL_MIN,
        "local_first": settings.LOCAL_FIRST,
        "cloud_llm_allowed": settings.CLOUD_LLM_ALLOWED,
    }
    last_autonomy = Path(settings.JANIS_PROJECT_DIR) / "data" / "autonomy_last.json"
    if last_autonomy.exists():
        try:
            autonomy_state["last_tick"] = json.loads(last_autonomy.read_text(encoding="utf-8"))
        except Exception:
            pass

    live_pipe = 0
    if manager.connections:
        live_pipe = 4
    elif (gpu.get("usage_pct") or 0) > 20:
        live_pipe = 2
    elif ollama.get("online"):
        live_pipe = 1

    return {
        "ok": True,
        "ts": int(time.time()),
        "metrics": {
            "hostname": platform.node(),
            "uptime_sec": boot_uptime,
            "cpu": {"usage_pct": ps["cpu_pct"], "temp_c": ps["temp_c"], "load_avg": ps["load_avg"]},
            "memory": {"usage_pct": ps["mem_pct"]},
            "gpu": gpu,
            "disk": ps["disk"],
            "network": ps["net"],
            "platform": platform.system(),
            "glances": glances is not None,
            "sidecars": sidecars,
            "process_uptime_sec": int(time.time() - _boot),
        },
        "inventory": inv,
        "status": {
            "service": "JANIS",
            "version": "2.0.0",
            "runtime_api": True,
            "paid_mode": rt.paid_mode,
            "reasoning_provider": rt.reasoning_provider,
            "ollama": ollama,
            "mac_node": mac,
            "fleet": fleet_manager.fleet_status(),
            "presence": presence.get_presence(),
            "stt": {"ready": stt.get("ready"), "engine": stt.get("engine")},
            "pocket_api": {
                "ingest": "/api/pocket/ingest",
                "telemetry": "/api/pocket/telemetry",
                "vision": "/api/pocket/vision",
                "push_register": "/api/pocket/push/register",
                "stt": "/api/stt",
                "claim": "/api/presence/claim",
                "ios_pending": "/api/devices/ios/pending",
                "identity_verify": "/api/identity/verify",
                "emergency_sos": "/api/emergency/sos",
            },
            "orchestrator": orch,
            "llm_provider": llm_prov,
            "llm_usage": usage,
            "paid_capabilities": list_capabilities(),
            "channel_skills": skills,
            "active_client": manager.active,
            "connected_clients": list(manager.connections.keys()),
            "session_messages": len(get_session_history()),
            "brain_version": 5,
            "scheduler": sched,
        },
        "knowledge": {
            **get_knowledge_stats(),
            "graph_nodes": kg.get("count", 0),
            "graph_edges": len(kg.get("edges", [])),
            "graph_user_nodes": kg_user,
            "graph_janis_nodes": kg_janis,
            "graph_sample": kg.get("nodes", [])[:12],
        },
        "scout": {
            "total": len(scout_items),
            "by_status": by_status,
            "recent": scout_items[:6],
        },
        "gaps": {"stats": gaps_s, "open": open_gaps},
        "win_vm": win,
        "tools": list_tools(),
        "tools_active": list_active_tools(),
        "mcp": mcp,
        "reasoning": {
            "provider": (rt.reasoning_provider or "ollama").upper(),
            "tier": (orch.get("default_tier") or "local").upper(),
            "mode": (orch.get("mode") or "local").upper(),
            "cloud_blocked": bool(orch.get("cloud_blocked")),
            "pipeline": ["INPUT", "THINK", "TOOLS", "AGENTS", "OUT"],
            "live_step": live_pipe,
            "tool_count": len(list_tools()),
            "active_tool_count": len(list_active_tools()),
        },
        "perception": perception,
        "peripherals": inv.get("peripherals") or {},
        "llm_models": llm_probe,
        "evolve": {
            "workspaces": evolve_paths,
            "proposals_open": len(open_proposals),
            "proposals": open_proposals[:6],
            "gaps_open": gaps_s.get("open", 0),
            "scout_total": len(scout_items),
            "autonomy": autonomy_state,
            "scheduler": sched,
            "lab": lab,
        },
    }
