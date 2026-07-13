"""Motore di auto-riflessione JANIS.

Ciclo evolutivo (semi-autonomo):
1. Osserva — legge chat recenti + gap aperti.
2. Riflette — un LLM analizza errori, schemi d'uso, preferenze dell'utente.
3. Impara — salva preferenze dedotte (auto-applicate, reversibili).
4. Propone — migliorie di codice/tool/UX restano in attesa di approvazione utente.

Le preferenze auto-apprese vengono iniettate nel system prompt come direttive,
senza modificare il codice. Le proposte tecniche NON vengono applicate da sole.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.Reflect")


def _data_dir() -> Path:
    p = Path(settings.MEMORY_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _proposals_file() -> Path:
    return _data_dir() / "reflect_proposals.json"


def _reflections_file() -> Path:
    return _data_dir() / "reflect_log.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Proposte (migliorie tecniche in attesa di approvazione)
# --------------------------------------------------------------------------- #
def _load_proposals() -> list[dict]:
    f = _proposals_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_proposals(items: list[dict]) -> None:
    _proposals_file().write_text(
        json.dumps(items[-200:], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_proposals(status: str | None = None) -> list[dict]:
    items = _load_proposals()
    if status:
        items = [p for p in items if p.get("status") == status]
    return list(reversed(items))


def add_proposal(title: str, detail: str, ptype: str, priority: str) -> dict:
    items = _load_proposals()
    # dedup per titolo+tipo ancora aperti
    norm = title.strip().lower()
    for p in items:
        if p.get("status") == "open" and p.get("title", "").strip().lower() == norm:
            return p
    entry = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "detail": (detail or "").strip(),
        "type": ptype,
        "priority": priority,
        "status": "open",
        "created_at": _now(),
        "decided_at": None,
    }
    items.append(entry)
    _save_proposals(items)
    return entry


def decide_proposal(proposal_id: str, accept: bool) -> dict | None:
    items = _load_proposals()
    for p in items:
        if p.get("id") == proposal_id:
            p["status"] = "accepted" if accept else "rejected"
            p["decided_at"] = _now()
            _save_proposals(items)
            return p
    return None


def _log_reflection(summary: str, n_prefs: int, n_props: int) -> None:
    f = _reflections_file()
    try:
        log = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except Exception:
        log = []
    log.append({
        "ts": _now(),
        "summary": summary,
        "preferences_learned": n_prefs,
        "proposals_added": n_props,
    })
    f.write_text(json.dumps(log[-100:], ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Raccolta osservazioni
# --------------------------------------------------------------------------- #
def _gather_recent_chat(max_msgs: int = 60) -> list[dict]:
    from backend.core.chat_store import list_sessions, load_messages

    msgs: list[dict] = []
    for sess in list_sessions(limit=5):
        sid = sess.get("session_id")
        if not sid:
            continue
        msgs.extend(load_messages(sid, limit=max_msgs))
        if len(msgs) >= max_msgs:
            break
    return msgs[-max_msgs:]


def _gather_open_gaps(limit: int = 20) -> list[dict]:
    from backend.core.capability_gaps import list_gaps

    return list_gaps(status="open")[:limit]


def _format_observations(chat: list[dict], gaps: list[dict]) -> str:
    lines = ["## Conversazioni recenti (utente ⇄ JANIS)"]
    if not chat:
        lines.append("(nessuna conversazione registrata)")
    for m in chat[-40:]:
        role = "Utente" if m.get("role") == "user" else "JANIS"
        text = str(m.get("content", "")).replace("\n", " ")[:280]
        if text:
            lines.append(f"- {role}: {text}")

    lines.append("\n## Gap / errori aperti")
    if not gaps:
        lines.append("(nessun gap aperto)")
    for g in gaps:
        lines.append(
            f"- [{g.get('severity', 'medium')}] {g.get('description', '')[:200]}"
            + (f" (tool: {g.get('tool')})" if g.get("tool") else "")
        )
    return "\n".join(lines)


_REFLECT_PROMPT = """Sei il modulo di auto-riflessione di JANIS, un assistente AI personale.
Analizza le osservazioni qui sotto e produci un'autovalutazione utile alla crescita di JANIS.

Obiettivi:
1. Dedurre PREFERENZE dell'utente (come vuole le risposte, abitudini, vincoli, strumenti preferiti, lingua, tono).
2. Proporre MIGLIORIE concrete per JANIS (prompt, tool, codice, UX) basate su errori o attriti osservati.

Rispondi SOLO con JSON valido in questo schema, senza testo extra:
{{
  "preferences": [
    {{"text": "preferenza chiara in italiano, una frase", "confidence": "high|medium|low"}}
  ],
  "improvements": [
    {{"title": "titolo breve", "detail": "cosa migliorare e perché", "type": "prompt|tool|code|ux", "priority": "P0|P1|P2"}}
  ],
  "summary": "1-2 frasi di sintesi"
}}

Regole:
- Massimo 6 preferenze e 6 migliorie.
- Le preferenze devono essere generali e durature, non dettagli di una singola frase.
- Non inventare: se non emerge nulla, restituisci liste vuote.

## OSSERVAZIONI
{observations}
"""


def _parse_json(raw: str) -> dict:
    if not raw:
        return {}
    # estrai blocco JSON
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    chunk = m.group(0)
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        # ripulisci eventuali backtick / fence
        chunk = chunk.strip().strip("`")
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            return {}


# --------------------------------------------------------------------------- #
# Ciclo principale
# --------------------------------------------------------------------------- #
async def run_reflection(*, dry_run: bool = False, max_msgs: int = 60) -> dict:
    """Esegue un ciclo di riflessione. Preferenze auto-applicate, migliorie in proposta."""
    from backend.core.llm_router import chat as llm_chat

    chat_msgs = _gather_recent_chat(max_msgs)
    gaps = _gather_open_gaps()

    if not chat_msgs and not gaps:
        return {
            "ok": True,
            "summary": "Niente da analizzare: nessuna chat o gap recente.",
            "preferences": [],
            "proposals": [],
            "dry_run": dry_run,
        }

    observations = _format_observations(chat_msgs, gaps)
    prompt = _REFLECT_PROMPT.format(observations=observations)

    try:
        raw, provider = await llm_chat([
            {"role": "system", "content": "Rispondi solo con JSON valido."},
            {"role": "user", "content": prompt},
        ])
    except Exception as e:
        logger.exception("Reflection LLM call failed")
        return {"ok": False, "error": str(e), "preferences": [], "proposals": []}

    parsed = _parse_json(raw)
    prefs = parsed.get("preferences") or []
    improvements = parsed.get("improvements") or []
    summary = (parsed.get("summary") or "").strip() or "Riflessione completata."

    applied_prefs: list[str] = []
    new_proposals: list[dict] = []

    if not dry_run:
        # Preferenze: auto-applicate (semi-autonomia) — salvate come direttive apprese
        from backend.core.tools.memory_tool import remember

        for p in prefs[:6]:
            text = (p.get("text") or "").strip() if isinstance(p, dict) else str(p).strip()
            conf = (p.get("confidence") or "medium") if isinstance(p, dict) else "medium"
            if not text or conf == "low":
                continue
            await remember({
                "text": text,
                "tags": ["preferenza", "auto-appresa", f"confidence-{conf}"],
                "source": "janis",
            })
            applied_prefs.append(text)

        # Migliorie: proposte in attesa di approvazione (codice non auto-applicato)
        for imp in improvements[:6]:
            if not isinstance(imp, dict):
                continue
            title = (imp.get("title") or "").strip()
            if not title:
                continue
            entry = add_proposal(
                title=title,
                detail=imp.get("detail") or "",
                ptype=(imp.get("type") or "ux").strip().lower(),
                priority=(imp.get("priority") or "P2").strip().upper(),
            )
            new_proposals.append(entry)

        _log_reflection(summary, len(applied_prefs), len(new_proposals))

    return {
        "ok": True,
        "provider": provider if not dry_run else None,
        "summary": summary,
        "preferences": applied_prefs if not dry_run else [
            (p.get("text") if isinstance(p, dict) else str(p)) for p in prefs
        ],
        "proposals": new_proposals if not dry_run else improvements,
        "dry_run": dry_run,
    }


def get_learned_preferences_context(limit: int = 12) -> str | None:
    """Direttive apprese da iniettare nel system prompt (semi-autonomia)."""
    from backend.core.tools.memory_tool import get_memories_by_tags

    prefs = get_memories_by_tags(["preferenza"], limit=limit)
    if not prefs:
        return None
    lines = [
        "=== PREFERENZE APPRESE DELL'UTENTE (OBBLIGATORIE — sovrascrivono tono default) ===",
        "Applica queste regole in OGNI risposta final, anche se contraddicono la persona base:",
    ]
    for p in prefs:
        text = (p.get("text") or "").strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if len(lines) > 1 else None
