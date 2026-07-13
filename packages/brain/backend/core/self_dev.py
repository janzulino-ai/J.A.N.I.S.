"""Stato progetti auto-sviluppo JANIS — brief, decisioni, fasi."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.SelfDev")

DEFAULT_OPEN_QUESTIONS = [
    {
        "id": "coordinator",
        "question": "Quale macchina fa da coordinatore (cervello + memoria)? Mac Mini o Windows?",
        "options": ["mac-mini", "windows"],
    },
    {
        "id": "network",
        "question": "Rete tra i PC: solo LAN di casa o Tailscale?",
        "options": ["lan", "tailscale"],
    },
    {
        "id": "power_model",
        "question": "Modello accensione: entrambi sempre accesi insieme, o Mac Mini always-on?",
        "options": ["both_together", "mac_always_on"],
    },
    {
        "id": "first_tool",
        "question": "Primo tool remoto dopo registro nodi?",
        "options": ["terminal", "filesystem", "browser"],
    },
]

PROJECT_ROOT = Path(settings.JANIS_PROJECT_DIR)
STATE_PATH = PROJECT_ROOT / "data" / "self_dev" / "project_state.json"
FLEET_SPEC_PATH = PROJECT_ROOT / "docs" / "FLEET_PROJECT.md"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_fleet_state() -> dict:
    """Garantisce open_questions coerenti con decisioni e migra chiavi legacy."""
    state = load_state()
    valid_ids = {q["id"] for q in DEFAULT_OPEN_QUESTIONS}
    legacy_map = {"coordinator machine": "coordinator"}

    raw = state.get("decisions") or {}
    merged: dict = {}
    had_legacy = False
    for key, val in raw.items():
        kid = legacy_map.get(str(key).lower().strip(), str(key).lower().strip())
        if kid in valid_ids:
            if str(key).lower().strip() != kid:
                had_legacy = True
            merged[kid] = val
        elif str(key).lower().strip() in valid_ids:
            merged[str(key).lower().strip()] = val

    # sync una tantum da chat utente (sessione Fleet già completata)
    if had_legacy and not state.get("fleet_chat_synced"):
        for qid, ans in (
            ("coordinator", "windows"),
            ("network", "lan"),
            ("power_model", "mac_always_on"),
            ("first_tool", "terminal"),
        ):
            if qid not in merged:
                merged[qid] = {"answer": ans, "at": _now(), "note": "sync chat utente"}
        state["fleet_chat_synced"] = True

    state["decisions"] = merged
    answered = set(merged.keys()) & valid_ids
    state["open_questions"] = [q for q in DEFAULT_OPEN_QUESTIONS if q["id"] not in answered]
    if state.get("phase", 0) == 0 and not state["open_questions"]:
        state["phase_label"] = "Decisioni complete — pronta fase 1"
    save_state(state)
    return state


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"active_project": "fleet", "phase": 0, "decisions": {}, "open_questions": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("project_state invalid: %s", e)
        return {"active_project": "fleet", "phase": 0, "decisions": {}, "open_questions": []}


def save_state(state: dict) -> dict:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def load_fleet_spec(max_chars: int = 14_000) -> str:
    if not FLEET_SPEC_PATH.exists():
        return "(FLEET_PROJECT.md non trovato)"
    text = FLEET_SPEC_PATH.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n… (troncato)"
    return text


_QUESTION_ID_BY_INDEX = {
    "1": "coordinator",
    "2": "network",
    "3": "power_model",
    "4": "first_tool",
}


def record_decision(question_id: str, answer: str, note: str = "") -> dict:
    state = ensure_fleet_state()
    qid = _QUESTION_ID_BY_INDEX.get(str(question_id).strip(), str(question_id).strip()).lower()
    decisions = state.setdefault("decisions", {})
    decisions[qid] = {"answer": answer, "at": _now(), "note": note}
    open_q = state.get("open_questions") or []
    state["open_questions"] = [q for q in open_q if q.get("id") != qid]
    return save_state(state)


def advance_phase(phase: int, label: str, summary: str = "") -> dict:
    state = load_state()
    prev = state.get("phase", 0)
    if prev and prev not in (state.get("completed_phases") or []):
        completed = state.setdefault("completed_phases", [])
        if prev not in completed:
            completed.append(prev)
    state["phase"] = phase
    state["phase_label"] = label
    if summary:
        notes = state.setdefault("notes", [])
        notes.append({"at": _now(), "phase": phase, "summary": summary[:2000]})
        state["notes"] = notes[-50:]
    state["last_cursor_session"] = _now()
    return save_state(state)


def mark_phase_complete(phase: int, label: str = "", summary: str = "") -> dict:
    """Segna una fase Fleet come completata (post-verifica implementazione)."""
    state = load_state()
    completed = state.setdefault("completed_phases", [])
    if phase not in completed:
        completed.append(phase)
    state["phase"] = phase
    state["phase_label"] = label or f"Fase {phase} completata"
    if summary:
        notes = state.setdefault("notes", [])
        notes.append({"at": _now(), "phase": phase, "summary": summary[:2000]})
        state["notes"] = notes[-50:]
    return save_state(state)


def get_context_for_brain() -> str:
    """Iniettato nel system prompt quando l'utente chiede auto-sviluppo."""
    state = load_state()
    decisions = state.get("decisions") or {}
    open_q = state.get("open_questions") or []
    lines = [
        "=== PROGETTO AUTO-SVILUPPO ATTIVO: JANIS Fleet ===",
        f"Fase corrente: {state.get('phase', 0)} — {state.get('phase_label', '?')}",
        f"Decisioni utente: {json.dumps(decisions, ensure_ascii=False) if decisions else 'nessuna ancora'}",
    ]
    if open_q:
        lines.append("DOMANDE APERTE (chiedi all'utente con {\"final\": \"...\"} PRIMA di cursor_code):")
        for q in open_q[:6]:
            opts = ", ".join(q.get("options") or [])
            lines.append(f"  - [{q.get('id')}]: {q.get('question')} (opzioni: {opts})")
    else:
        lines.append("Tutte le decisioni raccolte — puoi procedere con self_develop action=implement_phase.")
    lines.append(f"Spec completa: leggi docs/FLEET_PROJECT.md o usa self_develop action=status")
    return "\n".join(lines)


def build_cursor_prompt(phase: int, task_detail: str = "") -> str:
    state = load_state()
    spec = load_fleet_spec()
    decisions = json.dumps(state.get("decisions") or {}, ensure_ascii=False, indent=2)
    completed = state.get("completed_phases") or []

    return f"""Implementa JANIS Fleet — Fase {phase} nel repository JANIS.

## Spec progetto
{spec}

## Decisioni utente (rispettare)
{decisions}

## Fasi già completate
{completed}

## Task specifico fase {phase}
{task_detail or "Segui la sezione Fasi implementazione in FLEET_PROJECT.md per questa fase."}

## Istruzioni
- Lavora in JANIS_PROJECT_DIR
- Diff minimi, stile codebase esistente (FastAPI, @register tools, frontend JS)
- Una fase per sessione; non saltare fasi future
- Verifica: python -c "from backend.main import app"
- Documenta in data/self_dev/project_state.json solo via tool self_develop, non manualmente
"""


SELF_DEV_KEYWORDS = (
    "flotta", "fleet", "fase 1", "fase 2", "fase 3", "fase 4", "fase 5",
    "implement_phase", "self_develop", "FLEET_PROJECT",
    "mac mini", "bridge mac", "mac bridge", "nodi mac",
    "super partes", "cursor api", "in te stessa", "in sé stessa",
    "implementa fase", "sviluppa fase", "progetto fleet",
)
