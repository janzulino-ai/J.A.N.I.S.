"""Archiviazione chat e rielaborazione in memoria long-term."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.ChatArchive")

INDEX_NAME = "archive_index.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _index_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "chat" / INDEX_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_index() -> dict:
    path = _index_path()
    if not path.exists():
        return {"sessions": {}, "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("sessions", {})
        return data
    except Exception as e:
        logger.warning("archive index invalid: %s", e)
        return {"sessions": {}, "updated_at": None}


def _save_index(data: dict) -> None:
    data["updated_at"] = _now()
    _index_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_session_processed(session_id: str) -> bool:
    return session_id in (_load_index().get("sessions") or {})


def archive_stats() -> dict:
    from backend.core.chat_store import list_sessions

    index = _load_index()
    processed = index.get("sessions") or {}
    all_sessions = list_sessions(limit=500)
    pending = [s for s in all_sessions if s["session_id"] not in processed]
    return {
        "total_sessions": len(all_sessions),
        "processed": len(processed),
        "pending": len(pending),
        "pending_sessions": [s["session_id"] for s in pending[:20]],
        "updated_at": index.get("updated_at"),
    }


def _user_topics(messages: list[dict], limit: int = 12) -> list[str]:
    topics: list[str] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        line = " ".join(str(msg.get("content", "")).split())
        if len(line) < 8:
            continue
        topics.append(line[:160])
        if len(topics) >= limit:
            break
    return topics


async def _remember(text: str, tags: list[str]) -> str | None:
    from backend.core.tools.registry import execute_tool

    try:
        return await execute_tool(
            "remember",
            {"text": text, "tags": tags, "source": "janis"},
        )
    except Exception as e:
        logger.warning("remember from archive failed: %s", e)
        return None


async def reprocess_session(session_id: str, *, force: bool = False) -> dict:
    """
    Distilla una sessione chat in memoria long-term.
    Idempotente: salta sessioni già processate salvo force=True.
    """
    from backend.core.chat_store import get_history
    from backend.core.fleet_decisions import try_capture_fleet_decision
    from backend.core.tools.memory_tool import parse_inline_remember

    sid = session_id.strip()
    if not sid:
        return {"ok": False, "error": "session_id vuoto"}

    if not force and is_session_processed(sid):
        return {"ok": True, "session_id": sid, "skipped": True, "reason": "already_processed"}

    data = get_history(sid, limit=10_000)
    messages = data.get("messages") or []
    if not messages:
        return {"ok": False, "session_id": sid, "error": "sessione vuota"}

    extracted: list[str] = []
    fleet_hits = 0
    remember_hits = 0

    for msg in messages:
        if msg.get("role") != "user":
            continue
        text = str(msg.get("content") or "").strip()
        if not text:
            continue

        inline = parse_inline_remember(text)
        if inline:
            result = await _remember(inline, ["regola", "user", "chat-archive", f"session-{sid}"])
            if result:
                remember_hits += 1
                extracted.append(f"remember: {inline[:120]}")
            continue

        fleet = try_capture_fleet_decision(text)
        if fleet:
            fleet_hits += 1
            extracted.append(f"fleet [{fleet['question_id']}={fleet['answer']}]")

    topics = _user_topics(messages)
    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

    summary_lines = [
        f"[Chat {sid}] Sessione archiviata: {len(messages)} messaggi "
        f"({user_count} utente, {assistant_count} JANIS).",
    ]
    if topics:
        summary_lines.append("Temi principali:")
        for i, t in enumerate(topics[:8], 1):
            summary_lines.append(f"{i}. {t}")
    if extracted:
        summary_lines.append("Estratti automatici:")
        summary_lines.extend(f"• {x}" for x in extracted[:10])

    summary_text = "\n".join(summary_lines)
    summary_result = await _remember(
        summary_text,
        ["chat-archive", "session-summary", f"session-{sid}"],
    )

    index = _load_index()
    index.setdefault("sessions", {})[sid] = {
        "processed_at": _now(),
        "message_count": len(messages),
        "user_messages": user_count,
        "remember_extracted": remember_hits,
        "fleet_extracted": fleet_hits,
        "summary_preview": summary_text[:400],
        "remember_result": (summary_result or "")[:200],
    }
    _save_index(index)

    return {
        "ok": True,
        "session_id": sid,
        "message_count": len(messages),
        "remember_extracted": remember_hits,
        "fleet_extracted": fleet_hits,
        "topics": len(topics),
        "summary_saved": bool(summary_result),
    }


async def reprocess_pending(limit: int = 10) -> dict:
    from backend.core.chat_store import list_sessions

    pending = [
        s["session_id"]
        for s in list_sessions(limit=500)
        if not is_session_processed(s["session_id"])
    ][:limit]

    results = []
    for sid in pending:
        results.append(await reprocess_session(sid))

    ok = sum(1 for r in results if r.get("ok"))
    return {
        "ok": True,
        "processed": ok,
        "attempted": len(pending),
        "results": results,
        "stats": archive_stats(),
    }
