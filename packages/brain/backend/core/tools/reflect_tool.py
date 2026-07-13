"""Strumento di auto-riflessione — JANIS osserva, impara preferenze, propone migliorie."""
from __future__ import annotations

from backend.core.reflect import (
    decide_proposal,
    list_proposals,
    run_reflection,
)
from backend.core.tools.registry import register


@register("reflect")
async def reflect(args: dict) -> str:
    """Cicli di auto-riflessione e gestione proposte.

    action:
      - run: esegue una riflessione (preferenze auto-applicate, migliorie in proposta)
      - preview: come run ma senza salvare (dry-run)
      - proposals: elenca le proposte aperte
      - accept / reject: decide una proposta (richiede proposal_id)
    """
    action = (args.get("action") or "run").strip().lower()

    if action in ("run", "preview"):
        result = await run_reflection(dry_run=(action == "preview"))
        if not result.get("ok"):
            return f"Riflessione fallita: {result.get('error', 'errore sconosciuto')}"
        lines = [f"Sintesi: {result['summary']}"]
        prefs = result.get("preferences") or []
        props = result.get("proposals") or []
        if prefs:
            lines.append(f"\nPreferenze {'apprese' if action == 'run' else 'individuate'} ({len(prefs)}):")
            for p in prefs:
                lines.append(f"• {p}")
        if props:
            lines.append(f"\nProposte di miglioria ({len(props)}):")
            for pr in props:
                title = pr.get("title") if isinstance(pr, dict) else str(pr)
                prio = pr.get("priority", "") if isinstance(pr, dict) else ""
                lines.append(f"• [{prio}] {title}")
        if action == "preview":
            lines.append("\n(anteprima — nulla è stato salvato)")
        return "\n".join(lines)

    if action == "proposals":
        items = list_proposals(status="open")
        if not items:
            return "Nessuna proposta aperta."
        lines = ["Proposte aperte:"]
        for p in items:
            lines.append(f"• [{p['priority']}/{p['type']}] {p['title']} (id: {p['id'][:8]})")
        return "\n".join(lines)

    if action in ("accept", "reject"):
        pid = (args.get("proposal_id") or "").strip()
        if not pid:
            return "Errore: proposal_id obbligatorio."
        # accetta anche id abbreviato
        if len(pid) < 32:
            for p in list_proposals():
                if p["id"].startswith(pid):
                    pid = p["id"]
                    break
        decided = decide_proposal(pid, accept=(action == "accept"))
        if not decided:
            return f"Proposta {pid[:8]} non trovata."
        return f"Proposta '{decided['title']}' → {decided['status']}."

    return f"Azione '{action}' non riconosciuta. Usa: run, preview, proposals, accept, reject."
