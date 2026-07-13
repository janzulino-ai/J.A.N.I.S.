"""Self-improvement: propone fix e esegue comandi approvati via terminale/Cursor."""

from __future__ import annotations

import os

from backend.config import settings
from backend.core.capability_gaps import log_gap, resolve_gap
from backend.core.tools.registry import register


@register("cursor_terminal")
async def cursor_terminal(args: dict) -> str:
    """
    Registra un gap, propone una soluzione e opzionalmente la esegue.

    args:
      - description (required): cosa manca / cosa è fallito
      - proposed_command: comando shell da eseguire se approvato
      - execute: bool — esegui proposed_command (default False)
      - use_cursor: bool — delega a cursor_code se API key presente
      - cursor_prompt: prompt per Cursor Agent
      - cwd: directory di lavoro
      - gap_id: risolvi gap esistente dopo successo
    """
    description = (args.get("description") or args.get("gap") or "").strip()
    if not description:
        return "Errore: 'description' obbligatorio."

    proposed_command = (args.get("proposed_command") or args.get("command") or "").strip()
    execute = bool(args.get("execute", False))
    use_cursor = bool(args.get("use_cursor", False))
    cursor_prompt = (args.get("cursor_prompt") or description).strip()
    cwd = args.get("cwd") or settings.JANIS_PROJECT_DIR
    gap_id = args.get("gap_id")

    gap = log_gap(
        description,
        context=args.get("context"),
        tool="cursor_terminal",
        severity=args.get("severity", "medium"),
        proposed_fix=proposed_command or cursor_prompt,
    )

    if use_cursor:
        from backend.core.tools.cursor_agent import cursor_code

        if not settings.CURSOR_API_KEY:
            return (
                f"Gap registrato [{gap['id']}]. Cursor non configurato (CURSOR_API_KEY mancante).\n"
                f"Proposta: discuti con l'utente in Cursor e poi riesegui con execute=true.\n"
                f"Task: {cursor_prompt[:500]}"
            )
        result = await cursor_code({"prompt": cursor_prompt, "cwd": cwd})
        if gap_id:
            resolve_gap(gap_id, "Risolto via Cursor Agent")
        return f"Gap [{gap['id']}] — Cursor Agent:\n{result}"

    if execute and proposed_command:
        from backend.core.tools.terminal import run_terminal

        result = await run_terminal({"command": proposed_command, "cwd": cwd})
        if "exit: 0" in result or "exit:0" in result.replace(" ", ""):
            resolve_gap(gap["id"], f"Eseguito: {proposed_command[:200]}")
        return f"Gap [{gap['id']}] — Esecuzione approvata:\n{result}"

    lines = [
        f"Gap registrato: {gap['id']}",
        f"Descrizione: {description}",
    ]
    if proposed_command:
        lines.append(f"Comando proposto: {proposed_command}")
        lines.append(
            "Per eseguire: richiedi approvazione utente, poi richiama cursor_terminal "
            'con execute=true e lo stesso proposed_command.'
        )
    else:
        lines.append(
            "Nessun comando proposto. Discuti con l'utente via Cursor/terminale "
            "e registra proposed_command per la prossima iterazione."
        )
    if not settings.CURSOR_API_KEY:
        lines.append("Nota: CURSOR_API_KEY non configurato — auto-programmazione limitata.")
    return "\n".join(lines)
