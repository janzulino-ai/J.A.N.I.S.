"""Orchestrazione auto-sviluppo JANIS — plan, domande, cursor_code, memoria."""
from __future__ import annotations

from backend.config import settings
from backend.core.self_dev import (
    advance_phase,
    build_cursor_prompt,
    ensure_fleet_state,
    get_context_for_brain,
    load_fleet_spec,
    load_state,
    mark_phase_complete,
    record_decision,
    save_state,
)
from backend.core.tools.registry import register

QUESTION_ID_BY_INDEX = {
    "1": "coordinator",
    "2": "network",
    "3": "power_model",
    "4": "first_tool",
}

PHASE_TASKS = {
    1: (
        "Crea backend/core/fleet/ con manager nodi, router WS /ws/fleet-node in backend/routers/fleet.py, "
        "monta in main.py. Client bridge/bridge/client.py minimale (hello + heartbeat). "
        "UI: indicatore nodi in sidebar o stato sistema. Token MAC_BRIDGE_TOKEN in config."
    ),
    2: (
        "Tool fleet_execute che invia comandi al nodo connesso; streaming mac_stream verso UI; "
        "pannello mac-main in janis-panel.js; card agente Mac/Fleet in index.html e app.js."
    ),
    3: (
        "Memoria centralizzata: remember/recall preferiscono coordinatore; API sync opzionale /api/fleet/memory."
    ),
    4: (
        "Tool fleet_power + config/fleet.yaml.example (WOL MAC, host). Pulsanti wake/sleep in sidebar."
    ),
    5: (
        "Router super partes nel brain: scegli nodo per tool in base a capabilities e decisions in fleet.yaml."
    ),
}


@register("self_develop")
async def self_develop(args: dict, context: dict | None = None) -> str:
    """
    Auto-sviluppo JANIS via Cursor API.

    args:
      action: status | record_decision | implement_phase | read_spec
      question_id + answer — per record_decision
      phase — numero fase (1-5) per implement_phase
      task — override task opzionale per implement_phase
      note — nota aggiuntiva
    """
    action = str(args.get("action") or "status").lower().strip()
    ctx = context or {}
    on_event = ctx.get("on_event")

    if action == "status":
        state = ensure_fleet_state()
        open_q = state.get("open_questions") or []
        lines = [
            get_context_for_brain(),
            "",
            "---",
            f"PRO attivo richiesto per implement_phase. CURSOR_API_KEY: {'sì' if settings.CURSOR_API_KEY else 'no'}",
            f"Project dir: {settings.JANIS_PROJECT_DIR}",
        ]
        if open_q:
            lines.append(
                "\n⚠ Ci sono domande aperte: rispondi all'utente con final (testo), "
                "poi record_decision per ogni risposta, poi implement_phase."
            )
        else:
            lines.append(f"\n✓ Pronta per fase {state.get('phase', 0) + 1} — usa implement_phase.")
        return "\n".join(lines)

    if action == "read_spec":
        return load_fleet_spec()

    if action == "record_decision":
        qid = str(args.get("question_id") or args.get("id") or "").strip()
        qid = QUESTION_ID_BY_INDEX.get(qid, qid)
        answer = str(args.get("answer") or "").strip()
        note = str(args.get("note") or "").strip()
        if not qid or not answer:
            return "Errore: question_id e answer obbligatori per record_decision."
        state = record_decision(qid, answer, note)
        remaining = len(state.get("open_questions") or [])
        return (
            f"Decisione registrata [{qid}] = {answer}. "
            f"Domande aperte rimaste: {remaining}. "
            + ("Procedi con implement_phase fase 1." if remaining == 0 else "Chiedi le altre domande all'utente.")
        )

    if action == "implement_phase":
        state = ensure_fleet_state()
        open_q = state.get("open_questions") or []
        if open_q:
            ids = ", ".join(q.get("id", "?") for q in open_q)
            return (
                f"Non posso implementare: domande aperte ({ids}). "
                "Chiedi all'utente e usa record_decision per ogni risposta."
            )

        phase = int(args.get("phase") or (state.get("phase", 0) + 1))
        if phase < 1 or phase > 5:
            return "Errore: phase deve essere 1-5."

        task = str(args.get("task") or "").strip() or PHASE_TASKS.get(phase, "")
        prompt = build_cursor_prompt(phase, task)

        from backend.core.tools.cursor_agent import cursor_code

        result = await cursor_code(
            {"prompt": prompt, "cwd": settings.JANIS_PROJECT_DIR},
            context={"on_event": on_event} if on_event else None,
        )

        advance_phase(phase, f"Fase {phase} inviata a Cursor", summary=result[:500])

        from backend.core.tools.registry import execute_tool

        await execute_tool(
            "remember",
            {
                "text": (
                    f"Auto-sviluppo Fleet fase {phase}: inviato a Cursor Agent. "
                    f"Decisioni: {state.get('decisions')}. Esito breve: {result[:400]}"
                ),
                "tags": ["fleet", "self-dev", f"phase-{phase}"],
                "source": "janis",
            },
        )

        return f"Fase {phase} delegata a Cursor Agent.\n\n{result[:8000]}"

    if action == "set_phase":
        phase = int(args.get("phase", 0))
        label = str(args.get("label") or f"Fase {phase}")
        save_state({**load_state(), "phase": phase, "phase_label": label})
        return f"Fase impostata a {phase}: {label}"

    if action == "complete_phase":
        state = ensure_fleet_state()
        phase = int(args.get("phase") or state.get("phase", 0))
        if phase < 1 or phase > 5:
            return "Errore: phase deve essere 1-5."
        label = str(args.get("label") or f"Fase {phase} completata")
        summary = str(args.get("summary") or args.get("note") or "").strip()
        mark_phase_complete(phase, label, summary)
        return (
            f"Fase {phase} segnata completata ({label}). "
            f"Prossima: self_develop action=implement_phase phase={phase + 1}."
        )

    return (
        f"Azione sconosciuta: {action}. "
        "Usa: status, read_spec, record_decision, implement_phase, complete_phase."
    )
