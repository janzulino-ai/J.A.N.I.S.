"""Analisi tecnologica e pianificazione feature — JANIS fa ciò che fa l'assistente dev.

Ciclo:
1. inventory — cosa ha JANIS oggi (tool, doc, proposte, fleet)
2. research — confronta tecnologia/topic vs JANIS, salva analisi
3. roadmap — backlog prioritizzato (analisi + fleet + reflect)
4. to_proposals — spinge task in reflect_proposals
5. implement — delega un task ad autodev
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Analyze")

# Conoscenza base (OpenClaw / Odysseus) — punto di partenza onesto, aggiornabile con research
_KNOWN_SYSTEMS: dict[str, dict] = {
    "openclaw": {
        "name": "OpenClaw",
        "kind": "gateway agent",
        "strengths": [
            "WhatsApp/Telegram/Discord/Slack multi-canale",
            "Gateway always-on, messaggi in ingresso",
            "Gruppi con menzione e allowlist",
            "Cron/heartbeat, browser tool, skill ecosystem",
            "Self-hosted, agent-native",
        ],
        "weak_vs_janis": [
            "UI 3D/voce JANIS",
            "reflect/autodev integrati",
            "Fleet Mac custom",
        ],
        "urls": ["https://docs.openclaw.ai/", "https://github.com/openclaw/openclaw"],
    },
    "odysseus": {
        "name": "Odysseus (PewDiePie)",
        "kind": "local workspace",
        "strengths": [
            "Editor documenti, email IMAP, calendario/task",
            "Deep research multi-step, compare modelli",
            "MCP, shell, chat agent, memoria locale",
            "100% local-first workspace",
        ],
        "weak_vs_janis": [
            "Nessun WhatsApp/Telegram nativo",
            "Non è telecomando da telefono",
            "UI JANIS custom (pannelli, fleet)",
        ],
        "urls": ["https://github.com/pewdiepie-archdaemon/odysseus"],
    },
}


def _research_dir() -> Path:
    p = Path(settings.MEMORY_DIR) / "research"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def janis_inventory() -> dict:
    """Snapshot reale di cosa JANIS ha oggi."""
    from backend.core.reflect import list_proposals
    from backend.core.self_dev import load_state
    from backend.core.tools.registry import list_tools

    state = load_state()
    tools = list_tools()
    proposals_open = [p for p in list_proposals() if p.get("status") == "open"]
    docs = []
    docs_dir = Path(settings.JANIS_PROJECT_DIR) / "docs"
    if docs_dir.exists():
        docs = [f.name for f in sorted(docs_dir.glob("*.md"))]

    stubs = []
    if "whatsapp_send" in tools:
        stubs.append("whatsapp_send (stub)")

    return {
        "tools": tools,
        "stubs": stubs,
        "docs": docs,
        "fleet_phase": state.get("phase"),
        "fleet_completed": state.get("completed_phases") or [],
        "fleet_label": state.get("phase_label"),
        "open_proposals": len(proposals_open),
        "proposal_titles": [p.get("title") for p in proposals_open[:8]],
    }


def list_research() -> list[dict]:
    items: list[dict] = []
    for f in sorted(_research_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items


def _save_research(entry: dict) -> dict:
    rid = entry.get("id") or str(uuid.uuid4())
    entry["id"] = rid
    entry["updated_at"] = _now()
    path = _research_dir() / f"{rid}.json"
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


async def _fetch_url_snippet(url: str, max_chars: int = 4000) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "JANIS-Research/1.0"})
            if r.status_code != 200:
                return f"[HTTP {r.status_code}]"
            text = r.text
            # strip html roughly
            text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
    except Exception as e:
        return f"[fetch error: {e}]"


async def run_research(
    topic: str,
    *,
    references: list[str] | None = None,
    urls: list[str] | None = None,
) -> dict:
    """Analizza topic vs JANIS — come fa l'assistente dev, salva risultato."""
    from backend.core.llm_router import chat as llm_chat

    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "error": "topic obbligatorio"}

    inv = janis_inventory()
    refs = references or []
    ref_blocks: list[str] = []
    for key in refs:
        k = key.lower().strip()
        if k in _KNOWN_SYSTEMS:
            ref_blocks.append(json.dumps(_KNOWN_SYSTEMS[k], ensure_ascii=False, indent=2))
        elif k == "janis":
            ref_blocks.append(json.dumps(inv, ensure_ascii=False, indent=2))

    url_snips: list[str] = []
    for u in (urls or [])[:3]:
        snip = await _fetch_url_snippet(u)
        url_snips.append(f"URL {u}:\n{snip[:2000]}")

    prompt = f"""Sei l'analista tecnico di JANIS. Confronta e pianifica — niente marketing, niente bugie.

TOPIC: {topic}

INVENTARIO JANIS OGGI:
{json.dumps(inv, ensure_ascii=False, indent=2)}

RIFERIMENTI ESTERNI:
{chr(10).join(ref_blocks) if ref_blocks else "(nessuno)"}

{"FONTI WEB:" + chr(10).join(url_snips) if url_snips else ""}

Rispondi SOLO JSON valido:
{{
  "summary": "2-4 frasi sintetiche",
  "janis_has": ["..."],
  "janis_missing": ["..."],
  "borrow_from": "OpenClaw|Odysseus|entrambi|altro|nessuno",
  "priority": "P0|P1|P2",
  "effort": "basso|medio|alto",
  "tasks": [
    {{"title": "...", "detail": "...", "type": "code|tool|ux|prompt", "priority": "P0|P1|P2", "files_hint": ["path/opzionale"]}}
  ],
  "risks": ["..."],
  "ready_to_implement": true|false
}}
"""
    raw, provider = await llm_chat([
        {"role": "system", "content": "Analista software. JSON only. Italiano nei valori testuali."},
        {"role": "user", "content": prompt},
    ])
    parsed = _parse_json(raw or "")
    if not parsed:
        return {"ok": False, "error": "LLM non ha prodotto JSON valido", "raw": (raw or "")[:500]}

    entry = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "references": refs,
        "urls": urls or [],
        "provider": provider,
        "created_at": _now(),
        **parsed,
    }
    _save_research(entry)
    return {"ok": True, "research": entry}


def build_roadmap() -> list[dict]:
    """Backlog unificato: research tasks + fleet fasi + proposte reflect."""
    from backend.core.reflect import list_proposals

    items: list[dict] = []

    for r in list_research():
        for i, t in enumerate(r.get("tasks") or []):
            items.append({
                "source": "research",
                "research_id": r["id"],
                "topic": r.get("topic"),
                "task_index": i,
                "title": t.get("title"),
                "detail": t.get("detail"),
                "type": t.get("type", "code"),
                "priority": t.get("priority") or r.get("priority", "P2"),
                "files_hint": t.get("files_hint") or [],
                "status": t.get("status", "open"),
            })

    fleet_phases = [
        (2, "Fleet Fase 2 — fleet_execute remoto Mac"),
        (3, "Fleet Fase 3 — memoria centralizzata"),
        (4, "Fleet Fase 4 — power WOL/sleep"),
        (5, "Fleet Fase 5 — router LLM multi-nodo"),
    ]
    from backend.core.self_dev import load_state
    done = set(load_state().get("completed_phases") or [])
    for n, title in fleet_phases:
        if n not in done:
            items.append({
                "source": "fleet",
                "title": title,
                "priority": "P1" if n == 2 else "P2",
                "type": "code",
                "status": "open",
            })

    for p in list_proposals():
        if p.get("status") == "open":
            items.append({
                "source": "reflect",
                "proposal_id": p["id"],
                "title": p.get("title"),
                "detail": p.get("detail"),
                "type": p.get("type"),
                "priority": p.get("priority", "P2"),
                "status": "open",
            })

    pri_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    items.sort(key=lambda x: pri_order.get(x.get("priority", "P2"), 9))
    return items


def research_to_proposals(research_id: str) -> list[dict]:
    """Spinge i task di un'analisi nelle proposte reflect (dedup)."""
    from backend.core.reflect import add_proposal

    created = []
    for r in list_research():
        if r["id"] != research_id and not r["id"].startswith(research_id):
            continue
        for t in r.get("tasks") or []:
            p = add_proposal(
                t.get("title") or "Task da analisi",
                t.get("detail") or r.get("summary", ""),
                t.get("type") or "code",
                t.get("priority") or r.get("priority") or "P2",
            )
            created.append(p)
        break
    return created


async def implement_roadmap_item(
    *,
    research_id: str | None = None,
    task_index: int = 0,
    proposal_id: str | None = None,
    restart: bool = False,
    emit=None,
) -> dict:
    """Implementa un item della roadmap via autodev."""
    from backend.core.autodev import autocode, autocode_proposal

    if proposal_id:
        return await autocode_proposal(proposal_id, restart=restart, emit=emit)

    for r in list_research():
        if research_id and r["id"] != research_id and not r["id"].startswith(research_id):
            continue
        tasks = r.get("tasks") or []
        if task_index >= len(tasks):
            return {"ok": False, "error": "task_index fuori range"}
        t = tasks[task_index]
        task = f"{t.get('title')}\n\n{t.get('detail')}\n\nContesto analisi: {r.get('summary', '')}"
        files = t.get("files_hint") or []
        return await autocode(task, files=files, restart=restart, emit=emit)

    return {"ok": False, "error": "research non trovata"}


def get_roadmap_context(limit: int = 8) -> str | None:
    """Inietta roadmap sintetica nel system prompt."""
    items = build_roadmap()[:limit]
    if not items:
        return None
    lines = ["=== ROADMAP FEATURE (analisi + fleet + reflect) ==="]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. [{it.get('priority')}/{it.get('source')}] {it.get('title')}")
    lines.append("Usa analyze (research/roadmap/implement) per analizzare e implementare come l'assistente dev.")
    return "\n".join(lines)


def seed_baseline_research() -> dict | None:
    """Carica analisi OpenClaw/Odysseus se non esiste già."""
    marker = _research_dir() / "_seed_openclaw_odysseus.json"
    if marker.exists():
        return None
    entry = {
        "id": "seed-openclaw-odysseus",
        "topic": "OpenClaw + Odysseus vs JANIS — gap e opportunità",
        "summary": (
            "OpenClaw copre canali chat (WhatsApp) e daemon always-on. "
            "Odysseus copre workspace desktop (email, doc, calendario). "
            "JANIS ha agente locale, reflect/autodev, Fleet Fase 1; mancano gateway canali e app verticali."
        ),
        "janis_has": [
            "UI+voce, terminal, memoria, Mac SSH, reflect, autodev, Fleet Fase 1",
        ],
        "janis_missing": [
            "Gateway WhatsApp/Telegram",
            "Messaggi in ingresso da canali",
            "Cron/briefing",
            "Email/calendario/doc editor",
            "Fleet Fase 2-5",
        ],
        "borrow_from": "entrambi",
        "priority": "P0",
        "effort": "alto",
        "tasks": [
            {
                "title": "Gateway canali WhatsApp/Telegram",
                "detail": "Bridge messaggi in/out verso brain.process_message. Allowlist, menzione gruppi.",
                "type": "code",
                "priority": "P0",
                "files_hint": ["backend/core/channels/", "backend/routers/"],
            },
            {
                "title": "Fleet Fase 2 — fleet_execute",
                "detail": "Esecuzione remota comandi su nodi Mac via WS.",
                "type": "code",
                "priority": "P1",
                "files_hint": ["backend/core/fleet/", "backend/core/tools/"],
            },
            {
                "title": "Cron e briefing proattivo",
                "detail": "Scheduler locale: task mattutini, notifica via canale o UI.",
                "type": "code",
                "priority": "P1",
                "files_hint": ["backend/core/scheduler.py"],
            },
            {
                "title": "Modulo email IMAP (stile Odysseus)",
                "detail": "Lettura/triage inbox, bozze risposta via LLM.",
                "type": "tool",
                "priority": "P2",
                "files_hint": ["backend/core/tools/email_tool.py"],
            },
        ],
        "risks": ["WhatsApp ToS/API", "sicurezza gruppi", "PC deve restare acceso"],
        "ready_to_implement": True,
        "created_at": _now(),
        "updated_at": _now(),
        "seed": True,
    }
    marker.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry
