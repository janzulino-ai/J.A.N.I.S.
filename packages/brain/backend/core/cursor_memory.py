"""Bridge memoria ↔ Cursor Agent — contesto pre-run e summary post-run."""
from __future__ import annotations

import os
import re
from datetime import datetime
import uuid

from backend.core.tools.memory_tool import _load, _normalize_tags, _save, get_memories_by_tags, search_memories_async


def _project_label(cwd: str | None) -> str:
    if not cwd:
        return "janis"
    base = os.path.basename(os.path.normpath(cwd)) or "project"
    return re.sub(r"\s+", "-", base.lower())


async def build_cursor_context(prompt: str, cwd: str | None = None) -> str:
    """Memorie rilevanti + contesto progetto da iniettare nel prompt Cursor."""
    query_parts = [(prompt or "")[:400]]
    label = _project_label(cwd)
    if label:
        query_parts.append(label)
    if cwd:
        query_parts.append(os.path.basename(cwd))

    query = " ".join(p for p in query_parts if p).strip()
    hits = await search_memories_async(query)

    if cwd:
        cwd_lower = cwd.lower()
        extra = [
            e for e in _load()
            if cwd_lower in str(e.get("folder", "")).lower()
            or label in (e.get("tags") or [])
        ]
        seen = {e.get("id") for e in hits}
        for e in extra[:6]:
            if e.get("id") not in seen:
                hits.append(e)
                seen.add(e.get("id"))

    if not hits:
        return ""

    lines = ["=== MEMORIA JANIS (contesto rilevante) ==="]
    for h in hits[:8]:
        text = (h.get("text") or "").strip()
        if text:
            lines.append(f"- {text[:320]}")
    lines.append("=== FINE MEMORIA — esegui il task sotto ===\n")
    return "\n".join(lines)


def save_cursor_outcome(
    prompt: str,
    output: str,
    *,
    cwd: str | None = None,
    status: str = "unknown",
    source: str = "cursor_code",
    decision: str | None = None,
    fix_applied: str | None = None,
    gap_resolved: str | None = None,
) -> dict:
    """Salva summary strutturato in long_term memory dopo un run Cursor."""
    label = _project_label(cwd)
    parts = [f"[Cursor/{label}] status={status}."]
    if decision:
        parts.append(f" Decisione: {decision[:200]}.")
    if fix_applied:
        parts.append(f" Fix: {fix_applied[:300]}.")
    if gap_resolved:
        parts.append(f" Gap risolto: {gap_resolved[:200]}.")
    parts.append(f" Task: {(prompt or '')[:180]}.")
    if output:
        parts.append(f" Esito: {output[:400]}.")

    text = "".join(parts)
    tags = _normalize_tags([
        "cursor",
        "cursor-memory",
        label,
        status,
        "autofix" if source == "autofix" else "code",
    ])

    entries = _load()
    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "tags": tags,
        "source": "janis",
        "timestamp": datetime.now().isoformat(),
    }
    if cwd:
        entry["folder"] = cwd
    entries.append(entry)
    _save(entries)
    return entry


def save_cursor_bridge_exchange(
    cursor_message: str,
    janis_reply: str,
    *,
    action: str | None = None,
) -> dict:
    """Registra scambio Cursor (IDE) ↔ JANIS via API/chat."""
    parts = [f"[Cursor↔JANIS] Cursor ha scritto: {(cursor_message or '')[:220]}."]
    if action:
        parts.append(f" Azione: {action[:120]}.")
    parts.append(f" JANIS ha risposto: {(janis_reply or '')[:280]}.")
    text = "".join(parts)
    tags = _normalize_tags(["cursor", "cursor-bridge", "cursor-session", "fleet"])
    entries = _load()
    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "tags": tags,
        "source": "janis",
        "timestamp": datetime.now().isoformat(),
    }
    entries.append(entry)
    _save(entries)
    return entry


def get_cursor_bridge_context(limit: int = 5) -> str | None:
    """Ultime interazioni Cursor↔JANIS per il system prompt."""
    sessions = get_memories_by_tags(["cursor-bridge", "cursor-session"], limit=limit)
    if not sessions:
        return None
    lines = ["=== SESSIONI CURSOR ↔ JANIS (API) ==="]
    for s in sessions:
        lines.append(f"• {s.get('text', '')[:360]}")
    lines.append(
        "Se l'utente chiede se hai parlato con Cursor, conferma usando questi log — "
        "Cursor può scriverti via API e tu rispondi; non è solo cursor_code."
    )
    return "\n".join(lines)
