"""Strumento analyze — JANIS analizza, pianifica e implementa feature come l'assistente dev."""
from __future__ import annotations

import json

from backend.core.tech_analysis import (
    build_roadmap,
    implement_roadmap_item,
    janis_inventory,
    list_research,
    research_to_proposals,
    run_research,
    seed_baseline_research,
)
from backend.core.tools.registry import register


@register("analyze")
async def analyze(args: dict, context: dict | None = None) -> str:
    """Analisi tecnologica e roadmap feature.

    action:
      - inventory: cosa ha JANIS oggi
      - research: analizza topic (topic, references[], urls[])
      - list: analisi salvate
      - roadmap: backlog prioritizzato (research + fleet + reflect)
      - to_proposals: research_id → proposte reflect
      - implement: research_id+task_index OPPURE proposal_id → autodev
    """
    action = (args.get("action") or "roadmap").strip().lower()
    emit = (context or {}).get("on_event")

    seed_baseline_research()

    if action == "inventory":
        inv = janis_inventory()
        return json.dumps(inv, ensure_ascii=False, indent=2)

    if action == "research":
        topic = (args.get("topic") or args.get("query") or "").strip()
        if not topic:
            return "Errore: 'topic' obbligatorio per research."
        refs = args.get("references") or args.get("refs") or []
        if isinstance(refs, str):
            refs = [r.strip() for r in refs.split(",") if r.strip()]
        urls = args.get("urls") or []
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        res = await run_research(topic, references=refs, urls=urls)
        if not res.get("ok"):
            return f"Analisi fallita: {res.get('error')}"
        r = res["research"]
        lines = [
            f"Analisi salvata [{r['id'][:8]}]",
            f"Sintesi: {r.get('summary', '')}",
            f"Manca a JANIS: {', '.join((r.get('janis_missing') or [])[:5])}",
            f"Priorità: {r.get('priority')} — effort: {r.get('effort')}",
            f"Task proposti: {len(r.get('tasks') or [])}",
        ]
        for i, t in enumerate(r.get("tasks") or []):
            lines.append(f"  {i}. [{t.get('priority')}] {t.get('title')}")
        lines.append("\nUsa analyze action=roadmap o action=implement per procedere.")
        return "\n".join(lines)

    if action == "list":
        items = list_research()
        if not items:
            return "Nessuna analisi salvata."
        lines = ["Analisi salvate:"]
        for r in items[:15]:
            lines.append(f"• [{r['id'][:8]}] {r.get('topic', '?')} — {r.get('priority', '?')}")
        return "\n".join(lines)

    if action == "roadmap":
        items = build_roadmap()
        if not items:
            return "Roadmap vuota. Usa analyze action=research con un topic."
        lines = ["Roadmap prioritizzata:"]
        for i, it in enumerate(items[:20], 1):
            lines.append(
                f"{i}. [{it.get('priority')}/{it.get('source')}] {it.get('title')}"
            )
        return "\n".join(lines)

    if action == "to_proposals":
        rid = (args.get("research_id") or args.get("id") or "").strip()
        if not rid:
            return "Errore: research_id obbligatorio."
        created = research_to_proposals(rid)
        return f"{len(created)} proposte create/aggiornate in reflect."

    if action == "implement":
        restart = bool(args.get("restart"))
        pid = (args.get("proposal_id") or "").strip()
        rid = (args.get("research_id") or "").strip()
        idx = int(args.get("task_index") or 0)
        res = await implement_roadmap_item(
            research_id=rid or None,
            task_index=idx,
            proposal_id=pid or None,
            restart=restart,
            emit=emit,
        )
        if res.get("ok"):
            return "Implementazione completata via autodev ✓"
        return f"Implementazione non riuscita: {res.get('error', 'errore')}"

    return (
        f"Azione '{action}' non riconosciuta. "
        "Usa: inventory, research, list, roadmap, to_proposals, implement."
    )
