"""Cattura automatica decisioni Fleet dalla chat — senza JSON LLM."""
from __future__ import annotations

import re

from backend.core.self_dev import (
    DEFAULT_OPEN_QUESTIONS,
    ensure_fleet_state,
    load_state,
    record_decision,
)

# Ordine fisso domande Fleet
FLEET_QUESTION_IDS = ("coordinator", "network", "power_model", "first_tool")

_ANSWER_ALIASES: dict[str, dict[str, str]] = {
    "coordinator": {
        "windows": "windows",
        "win": "windows",
        "pc windows": "windows",
        "mac-mini": "mac-mini",
        "mac mini": "mac-mini",
        "macmini": "mac-mini",
    },
    "network": {
        "lan": "lan",
        "rete locale": "lan",
        "locale": "lan",
        "domestica": "lan",
        "casa": "lan",
        "tailscale": "tailscale",
        "vpn": "tailscale",
    },
    "power_model": {
        "both_together": "both_together",
        "entrambi": "both_together",
        "insieme": "both_together",
        "mac_always_on": "mac_always_on",
        "mac mini sempre": "mac_always_on",
        "mac sempre": "mac_always_on",
        "sempre acceso": "mac_always_on",
        "always on": "mac_always_on",
    },
    "first_tool": {
        "terminal": "terminal",
        "filesystem": "filesystem",
        "file": "filesystem",
        "browser": "browser",
        "scegli tu": "terminal",
        "scegli": "terminal",
        "va bene": "terminal",
        "fai terminal": "terminal",
    },
}


def _next_open_question_id() -> str | None:
    state = ensure_fleet_state()
    open_ids = {q.get("id") for q in (state.get("open_questions") or [])}
    for qid in FLEET_QUESTION_IDS:
        if qid in open_ids:
            return qid
    return None


def _normalize_answer(question_id: str, text: str) -> str | None:
    lower = text.lower().strip()
    aliases = _ANSWER_ALIASES.get(question_id, {})
    for phrase, canonical in sorted(aliases.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            return canonical
    # match opzione esatta
    state = load_state()
    for q in state.get("open_questions") or DEFAULT_OPEN_QUESTIONS:
        if q.get("id") != question_id:
            continue
        for opt in q.get("options") or []:
            if opt.lower() in lower:
                return opt
    return None


def _parse_numbered_answer(text: str) -> tuple[str | None, str | None]:
    """Es. '1 windows', '2 rete locale', '3mac mini sempre acceso'."""
    m = re.match(r"^\s*([1-4])\s*(.+)?$", text.strip(), re.IGNORECASE)
    if not m:
        return None, None
    idx = int(m.group(1)) - 1
    if idx < 0 or idx >= len(FLEET_QUESTION_IDS):
        return None, None
    qid = FLEET_QUESTION_IDS[idx]
    rest = (m.group(2) or "").strip()
    return qid, rest


def try_capture_fleet_decision(user_text: str) -> dict | None:
    """
    Se l'utente risponde a una domanda Fleet aperta, registra la decisione.
    Ritorna {question_id, answer, remaining} o None.
    """
    text = (user_text or "").strip()
    if not text or len(text) > 200:
        return None

    ensure_fleet_state()
    qid, rest = _parse_numbered_answer(text)
    if not qid:
        qid = _next_open_question_id()
        if not qid:
            return None
        rest = text

    answer = _normalize_answer(qid, rest or text)
    if not answer and qid == _next_open_question_id():
        answer = _normalize_answer(qid, text)
    if not answer:
        return None

    record_decision(qid, answer)
    state = load_state()
    remaining = len(state.get("open_questions") or [])
    return {"question_id": qid, "answer": answer, "remaining": remaining}


def fleet_decisions_summary() -> str:
    state = ensure_fleet_state()
    decisions = state.get("decisions") or {}
    open_q = state.get("open_questions") or []
    lines = [f"Fase {state.get('phase', 0)} — {state.get('phase_label', '?')}"]
    if decisions:
        lines.append("Decisioni registrate:")
        for k, v in decisions.items():
            lines.append(f"  • [{k}] = {v.get('answer', v)}")
    if open_q:
        lines.append(f"Mancano {len(open_q)} decisioni:")
        for q in open_q:
            opts = ", ".join(q.get("options") or [])
            lines.append(f"  • [{q.get('id')}]: {opts}")
    else:
        lines.append("Tutte le decisioni raccolte — pronta per implement_phase fase 1.")
    return "\n".join(lines)


def all_fleet_decisions_complete() -> bool:
    state = ensure_fleet_state()
    return len(state.get("open_questions") or []) == 0
