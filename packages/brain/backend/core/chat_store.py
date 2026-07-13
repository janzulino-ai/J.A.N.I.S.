"""Persistenza chat session-based in data/chat/*.jsonl."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.config import settings

_active_session_id: str | None = None


def _chat_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "chat"
    p.mkdir(parents=True, exist_ok=True)
    return p


def current_session_id() -> str:
    global _active_session_id
    if not _active_session_id:
        _active_session_id = _new_session_id()
    return _active_session_id


def _new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def new_session() -> str:
    global _active_session_id
    _active_session_id = _new_session_id()
    return _active_session_id


def set_session(session_id: str) -> str:
    global _active_session_id
    _active_session_id = session_id.strip()
    return _active_session_id


def append_message(
    role: str,
    content: str,
    *,
    session_id: str | None = None,
    extra: dict | None = None,
) -> str:
    sid = session_id or current_session_id()
    record: dict = {
        "ts": datetime.now().isoformat(),
        "role": role,
        "content": content,
    }
    if extra:
        record.update(extra)
    path = _chat_dir() / f"{sid}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return sid


def load_messages(session_id: str | None = None, limit: int = 40) -> list[dict]:
    sid = session_id or current_session_id()
    path = _chat_dir() / f"{sid}.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    msgs: list[dict] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            role = rec.get("role")
            content = rec.get("content")
            if role and content is not None:
                msgs.append({"role": role, "content": content})
        except (json.JSONDecodeError, TypeError):
            continue
    return msgs


def list_sessions(limit: int = 30) -> list[dict]:
    sessions: list[dict] = []
    for path in sorted(_chat_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(sessions) >= limit:
            break
        sid = path.stem
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        count = sum(1 for ln in lines if ln.strip())
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        preview = ""
        for line in reversed(lines):
            try:
                rec = json.loads(line)
                if rec.get("role") == "user":
                    preview = str(rec.get("content", ""))[:80]
                    break
            except json.JSONDecodeError:
                continue
        sessions.append({
            "session_id": sid,
            "messages": count,
            "updated_at": mtime,
            "preview": preview,
        })
    return sessions


def get_history(session_id: str | None = None, limit: int = 100) -> dict:
    sid = session_id or current_session_id()
    path = _chat_dir() / f"{sid}.jsonl"
    items: list[dict] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {
        "session_id": sid,
        "messages": items,
        "count": len(items),
    }
