"""Autoconsapevolezza host — cosa JANIS può fare su questo server."""
from __future__ import annotations

import asyncio
import time
from typing import Any

_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_CACHE_TTL = 120.0

_AWARENESS_TRIGGERS = (
    "che hardware", "quale hardware", "hardware hai", "specifiche",
    "cosa puoi fare", "cosa sai fare", "quali funzioni", "quali strumenti",
    "quali tool", "cosa hai installato", "software installato",
    "periferiche", "usb", "cosa rilevi", "cosa hai a disposizione",
    "autoconsapevole", "capacità", "capability", "possibilità",
    "descrivi il server", "descrivi te stess", "chi sei",
    "llm funziona", "modello attivo", "ollama",
)


def is_awareness_query(text: str) -> bool:
    lower = (text or "").lower()
    return any(t in lower for t in _AWARENESS_TRIGGERS)


async def build_awareness(*, refresh_inventory: bool = False) -> dict[str, Any]:
    from backend.core.hud_dashboard import build_dashboard

    dash = await build_dashboard(refresh_inventory=refresh_inventory)
    inv = dash.get("inventory") or {}
    metrics = dash.get("metrics") or {}
    status = dash.get("status") or {}
    tools = dash.get("tools") or []
    mcp = dash.get("mcp") or {}
    gaps = dash.get("gaps") or {}
    win = dash.get("win_vm") or {}
    lp = status.get("llm_provider") or {}
    probe = lp.get("ollama_probe") or {}
    by_tier = probe.get("by_tier") or {}

    sidecars = metrics.get("sidecars") or {}
    ollama = status.get("ollama") or {}
    skills = (status.get("channel_skills") or {}).get("skills") or []
    caps = status.get("paid_capabilities") or []
    fleet = status.get("fleet") or {}
    sched = status.get("scheduler") or {}

    return {
        "hostname": inv.get("hostname") or metrics.get("hostname"),
        "platform": f"{inv.get('platform', 'Linux')} {inv.get('release', '')}".strip(),
        "arch": inv.get("arch"),
        "cpu": inv.get("cpu"),
        "memory_gb": inv.get("memory_gb"),
        "gpu": inv.get("gpu") or [],
        "usb_devices": inv.get("usb_devices", 0),
        "network": inv.get("network") or [],
        "block_devices": inv.get("block_devices") or [],
        "disks": [d for d in (inv.get("disks") or []) if not str(d.get("mount", "")).startswith("/snap")][:6],
        "sidecars": {
            "brain": sidecars.get("brain", True),
            "ollama": sidecars.get("ollama") or ollama.get("online"),
            "glances": sidecars.get("glances"),
            "litellm": sidecars.get("litellm"),
            "qdrant": sidecars.get("qdrant"),
            "stt": status.get("stt", {}).get("ready"),
        },
        "llm": {
            "active": lp.get("active"),
            "configured": lp.get("configured"),
            "model": lp.get("ollama_model"),
            "models": ollama.get("models") or [],
            "by_tier": by_tier,
            "fallback_chain": lp.get("fallback_chain") or [],
        },
        "tools": tools,
        "tool_count": len(tools),
        "mcp_servers": [s.get("name") for s in (mcp.get("mcp_servers") or [])],
        "channels": [
            {"id": s.get("id"), "ready": s.get("ready"), "capabilities": s.get("capabilities") or []}
            for s in skills
        ],
        "paid_capabilities": [
            {"name": c.get("name"), "tier": c.get("tier"), "key_present": c.get("key_present")}
            for c in caps
        ],
        "fleet": {
            "enabled": fleet.get("enabled"),
            "nodes_online": fleet.get("nodes_online"),
            "nodes_total": fleet.get("nodes_total"),
            "nodes": fleet.get("nodes") or [],
        },
        "mac_node": status.get("mac_node") or {},
        "win_vm": {
            "available": win.get("available"),
            "state": win.get("state"),
            "vnc": win.get("vnc"),
        },
        "scheduler": sched,
        "gaps_open": (gaps.get("stats") or {}).get("open", 0),
        "stt_engine": (status.get("stt") or {}).get("engine"),
        "pocket_api": list((status.get("pocket_api") or {}).keys()),
        "probed_at": inv.get("probed_at"),
    }


async def get_awareness_cached(*, refresh_inventory: bool = False) -> dict[str, Any]:
    now = time.time()
    if not refresh_inventory and _CACHE["data"] and now - _CACHE["ts"] < _CACHE_TTL:
        return _CACHE["data"]
    data = await build_awareness(refresh_inventory=refresh_inventory)
    _CACHE["ts"] = now
    _CACHE["data"] = data
    return data


def format_awareness_text(data: dict[str, Any]) -> str:
    cpu = data.get("cpu") or {}
    gpus = data.get("gpu") or []
    side = data.get("sidecars") or {}
    llm = data.get("llm") or {}
    lines = [
        "=== AUTOCONSAPEVOLEZZA HOST (live) ===",
        f"Host: {data.get('hostname')} · {data.get('platform')} · {data.get('arch')}",
        f"CPU: {cpu.get('model', '?')} · {cpu.get('cores_logical', '?')} thread",
        f"RAM: {data.get('memory_gb', '?')} GB · USB: {data.get('usb_devices', 0)} device",
    ]
    if gpus:
        for g in gpus:
            lines.append(f"GPU: {g.get('name', '?')} {g.get('vram', '')} {g.get('driver', '')}".strip())
    else:
        lines.append("GPU: nessuna NVIDIA rilevata (integrata o assente)")

    nics = data.get("network") or []
    if nics:
        nic_line = ", ".join(
            f"{n.get('name')}({', '.join((n.get('addresses') or [])[:2])})" for n in nics[:4]
        )
        lines.append(f"Rete: {nic_line}")

    disks = data.get("disks") or []
    if disks:
        lines.append("Dischi: " + "; ".join(
            f"{d.get('mount')} {d.get('used_pct')}% ({d.get('total_gb')}GB)" for d in disks[:4]
        ))

    blocks = data.get("block_devices") or []
    if blocks:
        lines.append("Block: " + ", ".join(
            f"{b.get('name')} {b.get('size')}" for b in blocks[:5]
        ))

    lines.append(
        f"Stack: brain={'ON' if side.get('brain') else 'OFF'} "
        f"ollama={'ON' if side.get('ollama') else 'OFF'} "
        f"glances={'ON' if side.get('glances') else 'OFF'} "
        f"litellm={'ON' if side.get('litellm') else 'OFF'} "
        f"qdrant={'ON' if side.get('qdrant') else 'OFF'} "
        f"stt={'ON' if side.get('stt') else 'OFF'}"
    )
    lines.append(
        f"LLM attivo: {llm.get('active', '?')} · modello {llm.get('model', '?')} "
        f"· modelli ollama: {', '.join(llm.get('models') or []) or '—'}"
    )
    bt = llm.get("by_tier") or {}
    if bt:
        lines.append(
            f"Modelli per tier (probe): fast={bt.get('fast') or '—'} "
            f"balanced={bt.get('balanced') or '—'} capable={bt.get('capable') or '—'}"
        )

    tools = data.get("tools") or []
    lines.append(f"Tool registrati ({len(tools)}): {', '.join(tools)}")

    mcp = data.get("mcp_servers") or []
    if mcp:
        lines.append(f"MCP server: {', '.join(mcp)}")

    ch = data.get("channels") or []
    if ch:
        lines.append("Canali: " + ", ".join(
            f"{c['id']}({'ready' if c.get('ready') else 'wait'})" for c in ch
        ))

    fleet = data.get("fleet") or {}
    lines.append(
        f"Fleet: {fleet.get('nodes_online', 0)}/{fleet.get('nodes_total', 0)} nodi online"
    )
    mac = data.get("mac_node") or {}
    lines.append(f"Mac SSH: {'ONLINE' if mac.get('online') else 'OFFLINE'}" + (f" — {mac.get('info', '')[:60]}" if mac.get('info') and not mac.get('online') else ""))

    win = data.get("win_vm") or {}
    if win.get("available"):
        lines.append(f"Win-VM: {win.get('state', '?')} · VNC {win.get('vnc', {}).get('host')}:{win.get('vnc', {}).get('port')}")
    else:
        lines.append(f"Win-VM: {win.get('state', 'non configurata')}")

    pocket = data.get("pocket_api") or []
    if pocket:
        lines.append(f"Pocket API: {', '.join(pocket)}")

    sched = data.get("scheduler") or {}
    if sched.get("enabled"):
        lines.append(f"Scheduler: {'running' if sched.get('running') else 'stop'} · {sched.get('enabled_jobs', 0)} job")

    lines.append(
        "USA QUESTI DATI quando l'utente chiede hardware, software, capacità o periferiche. "
        "Non inventare — se un dato manca, dillo."
    )
    return "\n".join(lines)


async def get_awareness_context_for_brain() -> str:
    try:
        data = await get_awareness_cached(refresh_inventory=False)
        text = format_awareness_text(data)
        # Prompt compatta — evita saturare gemma4 locale
        if len(text) > 2800:
            text = text[:2800] + "\n… (inventario troncato — usa host_capabilities)"
        return text
    except Exception:
        return ""


def build_awareness_reply_sync(data: dict[str, Any]) -> str:
    """Risposta utente per fast-path autonomy."""
    cpu = data.get("cpu") or {}
    llm = data.get("llm") or {}
    side = data.get("sidecars") or {}
    tools = data.get("tools") or []
    intro = (
        f"Sono JANIS sul server **{data.get('hostname')}** ({data.get('platform')}, {data.get('arch')}).\n\n"
        f"**Hardware:** {cpu.get('model', '?')}, {cpu.get('cores_logical', '?')} thread, "
        f"{data.get('memory_gb', '?')} GB RAM, {data.get('usb_devices', 0)} dispositivi USB.\n"
    )
    gpus = data.get("gpu") or []
    if gpus:
        intro += "**GPU:** " + "; ".join(g.get("name", "?") for g in gpus) + "\n"
    else:
        intro += "**GPU:** nessuna NVIDIA dedicata rilevata.\n"

    intro += (
        f"\n**Stack attivo:** Ollama={'sì' if side.get('ollama') else 'no'}, "
        f"LiteLLM={'sì' if side.get('litellm') else 'no'}, "
        f"Glances={'sì' if side.get('glances') else 'no'}, "
        f"Qdrant={'sì' if side.get('qdrant') else 'no'}, "
        f"STT={data.get('stt_engine') or 'off'}.\n"
        f"**LLM:** provider {llm.get('active')}, modello {llm.get('model')}.\n\n"
        f"**{len(tools)} strumenti** (terminal, file, memoria, fleet, scout, cursor, …) "
        f"e canali Pocket/Telegram/WhatsApp (stato variabile).\n"
        f"Chiedimi di eseguire qualcosa e uso il tool giusto."
    )
    return intro


async def answer_awareness_query(user_text: str) -> str:
    data = await get_awareness_cached(refresh_inventory="hardware" in user_text.lower() or "inventario" in user_text.lower())
    return build_awareness_reply_sync(data)
