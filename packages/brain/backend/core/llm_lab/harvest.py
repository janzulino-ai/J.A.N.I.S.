"""Raccolta conversazioni chat → dataset instruction/response."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.core.llm_lab.paths import harvest_state_path, lab_datasets_dir

logger = logging.getLogger("JANIS.Lab.Harvest")

_SKIP_MARKERS = (
    "Errore esecuzione",
    "non registrato",
    "Gap registrato",
    '{"tool":',
    '{"final":',
)


def _chat_dir() -> Path:
    return Path(settings.JANIS_PROJECT_DIR) / "data" / "chat"


def _load_state() -> dict:
    p = harvest_state_path()
    if not p.exists():
        return {"harvested_files": {}, "last_harvest_at": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"harvested_files": {}, "last_harvest_at": None}


def _save_state(state: dict) -> None:
    harvest_state_path().write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_chat_file(path: Path) -> list[dict]:
    rows: list[dict] = []
    messages: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    pending_user: str | None = None
    for msg in messages:
        role = (msg.get("role") or "").lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user:
            if _is_valid_pair(pending_user, content):
                rows.append({
                    "instruction": pending_user,
                    "input": "",
                    "output": content,
                    "source": path.name,
                })
            pending_user = None
    return rows


def _is_valid_pair(instruction: str, output: str) -> bool:
    if len(instruction) < 8 or len(output) < 20:
        return False
    if len(instruction) > 8000 or len(output) > 12000:
        return False
    if any(m in output for m in _SKIP_MARKERS):
        return False
    if output.startswith("{") and '"tool"' in output:
        return False
    return True


def _example_id(row: dict) -> str:
    key = f"{row.get('instruction', '')}|{row.get('output', '')[:200]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


async def harvest_chats(*, force_all: bool = False) -> dict:
    """Estrae coppie user/assistant da data/chat/*.jsonl."""
    chat_dir = _chat_dir()
    if not chat_dir.exists():
        return {"ok": False, "error": "cartella chat assente", "examples": 0}

    state = _load_state()
    harvested_files: dict = state.get("harvested_files") or {}
    all_rows: list[dict] = []
    files_processed = 0
    files_skipped = 0

    for path in sorted(chat_dir.glob("*.jsonl")):
        mtime = path.stat().st_mtime
        prev = harvested_files.get(path.name)
        if not force_all and prev and prev.get("mtime") == mtime:
            files_skipped += 1
            continue
        rows = _parse_chat_file(path)
        all_rows.extend(rows)
        harvested_files[path.name] = {"mtime": mtime, "pairs": len(rows)}
        files_processed += 1

    if not all_rows:
        state["last_harvest_at"] = datetime.now(timezone.utc).isoformat()
        state["harvested_files"] = harvested_files
        _save_state(state)
        return {
            "ok": True,
            "examples": 0,
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "output": None,
        }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = lab_datasets_dir() / f"harvest-{stamp}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            row["id"] = _example_id(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    state["last_harvest_at"] = datetime.now(timezone.utc).isoformat()
    state["harvested_files"] = harvested_files
    state["last_output"] = str(out_path)
    state["last_count"] = len(all_rows)
    _save_state(state)

    logger.info("Harvest: %d esempi da %d file", len(all_rows), files_processed)
    return {
        "ok": True,
        "examples": len(all_rows),
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "output": str(out_path),
    }
