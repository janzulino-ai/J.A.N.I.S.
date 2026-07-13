"""Strumento auto-sviluppo — auto-codice via Cursor con validazione e auto-riavvio."""
from __future__ import annotations

from backend.core.autodev import autocode, autocode_proposal
from backend.core.tools.registry import register


@register("autodev")
async def autodev(args: dict, context: dict | None = None) -> str:
    """Auto-codice JANIS.

    args:
      - proposal_id: esegue una proposta di reflect (verifica → codice → validazione)
      - task + files: corregge un problema descritto
      - restart: True per auto-riavvio dopo validazione OK
    """
    emit = (context or {}).get("on_event")
    restart = bool(args.get("restart"))

    proposal_id = (args.get("proposal_id") or "").strip()
    if proposal_id:
        res = await autocode_proposal(proposal_id, restart=restart, emit=emit)
    else:
        task = (args.get("task") or "").strip()
        if not task:
            return "Errore: serve 'task' oppure 'proposal_id'."
        files = args.get("files") or []
        if isinstance(files, str):
            files = [f.strip() for f in files.split(",") if f.strip()]
        res = await autocode(task, files=files, verify=bool(args.get("verify", True)), restart=restart, emit=emit)

    if not res.get("ok"):
        return f"Auto-codice non riuscito: {res.get('error', 'errore')}" + (
            " (file ripristinati dal backup)" if res.get("restored") else ""
        )
    lines = ["Auto-codice completato ✓"]
    if res.get("plan"):
        lines.append(f"\nPiano verificato (Cursor):\n{res['plan'][:600]}")
    lines.append(f"\nValidazione backend: {'OK' if res['validated'] else 'NO'}")
    if res.get("restarted"):
        lines.append("Backend riavviato automaticamente.")
    return "\n".join(lines)
