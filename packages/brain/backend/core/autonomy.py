"""
Pipeline autonomia JANIS — percorsi deterministici prima del LLM.

Percezione → decisione locale → azione (tool) → memoria → risposta utente.
Il modello locale serve solo per linguaggio naturale; routing critico è qui.
"""
from __future__ import annotations

import logging
import re
from typing import Awaitable, Callable

from backend.core.fleet_decisions import (
    all_fleet_decisions_complete,
    fleet_decisions_summary,
    try_capture_fleet_decision,
)
from backend.core.self_dev import DEFAULT_OPEN_QUESTIONS, ensure_fleet_state

logger = logging.getLogger("JANIS.Autonomy")

EventCallback = Callable[[dict], Awaitable[None]]

_IMPLEMENT_TRIGGERS = (
    "implementa", "procedi", "fase 1", "inizia fleet", "avvia fleet",
    "implement_phase", "inizia la fase", "fai la fase", "vai con fleet",
    "autoimplement", "auto-implement",
)

_SELF_DEV_STATUS = (
    "stato fleet", "stato auto", "stato autosviluppo", "decisioni fleet",
    "quante decisioni", "domande aperte",
)


def _wants_implement(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _IMPLEMENT_TRIGGERS)


def _wants_fleet_status(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _SELF_DEV_STATUS)


def _next_question_text() -> str | None:
    state = ensure_fleet_state()
    open_q = state.get("open_questions") or []
    if not open_q:
        return None
    q = open_q[0]
    opts = " / ".join(q.get("options") or [])
    return f"{q.get('question')}\nOpzioni: {opts}"


async def _run_implement_phase(emit: EventCallback, phase: int = 1) -> str:
    from backend.core.tools.registry import execute_tool

    await emit({"type": "state", "state": "WORKING"})
    result = await execute_tool(
        "self_develop",
        {"action": "implement_phase", "phase": phase},
        context={"on_event": emit},
    )
    return result or "Implementazione avviata."


async def process_autonomy(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
    deliver_final,
) -> str | None:
    """
    Gestisce Fleet, auto-implement e status senza passare da Ollama.
    Ritorna risposta finale se gestito, altrimenti None.
    """
    text = (user_text or "").strip()
    if not text:
        return None

    ensure_fleet_state()

    if _wants_fleet_status(text):
        msg = fleet_decisions_summary()
        return await deliver_final(msg, emit, stream_final)

    captured = try_capture_fleet_decision(text)
    if captured:
        qid = captured["question_id"]
        answer = captured["answer"]
        remaining = captured["remaining"]
        lines = [f"Ok, registrato [{qid}] = {answer}."]
        if remaining:
            nxt = _next_question_text()
            if nxt:
                lines.append(f"\nProssima domanda ({remaining} rimaste):\n{nxt}")
        else:
            lines.append("\nTutte le decisioni Fleet sono complete.")
            lines.append("Dimmi «procedi» o «implementa fase 1» per avviare Cursor Agent.")
            lines.append("\n" + fleet_decisions_summary())
        return await deliver_final("\n".join(lines), emit, stream_final)

    if all_fleet_decisions_complete() and _wants_implement(text):
        phase = 1
        m = re.search(r"fase\s*(\d)", text.lower())
        if m:
            phase = max(1, min(5, int(m.group(1))))
        msg = await _run_implement_phase(emit, phase)
        return await deliver_final(msg, emit, stream_final)

    return None
