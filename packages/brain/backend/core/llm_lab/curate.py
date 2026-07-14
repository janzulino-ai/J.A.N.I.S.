"""Curazione dataset — filtro qualità, dedup, PII base."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.core.llm_lab.paths import curated_dataset_path, lab_datasets_dir

logger = logging.getLogger("JANIS.Lab.Curate")

_PII_PATTERNS = (
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"),
)
_BAD_OUTPUT = (
    "non so",
    "non posso",
    "errore:",
    "failed",
    "exception",
    "timed out",
)


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _row_id(row: dict) -> str:
    if row.get("id"):
        return row["id"]
    key = f"{row.get('instruction', '')}|{row.get('output', '')[:300]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _scrub_pii(text: str) -> str:
    out = text
    for pat in _PII_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _quality_ok(row: dict) -> bool:
    inst = (row.get("instruction") or "").strip()
    out = (row.get("output") or "").strip()
    if len(inst) < 8 or len(out) < 30:
        return False
    low = out.lower()
    if sum(1 for b in _BAD_OUTPUT if b in low) >= 2:
        return False
    return True


async def curate_dataset(*, include_harvest: bool = True) -> dict:
    """Unisce harvest + curated esistente, dedup, salva curated.jsonl."""
    seen: set[str] = set()
    merged: list[dict] = []

    # Parte dal curated esistente
    for row in _load_jsonl(curated_dataset_path()):
        rid = _row_id(row)
        if rid in seen:
            continue
        seen.add(rid)
        merged.append(row)

    added = 0
    if include_harvest:
        for path in sorted(lab_datasets_dir().glob("harvest-*.jsonl")):
            for row in _load_jsonl(path):
                if not _quality_ok(row):
                    continue
                rid = _row_id(row)
                if rid in seen:
                    continue
                seen.add(rid)
                row["instruction"] = _scrub_pii(row.get("instruction") or "")
                row["output"] = _scrub_pii(row.get("output") or "")
                row["id"] = rid
                merged.append(row)
                added += 1

    out = curated_dataset_path()
    with out.open("w", encoding="utf-8") as f:
        for row in merged:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta = {
        "curated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(merged),
        "added": added,
        "path": str(out),
    }
    meta_path = lab_datasets_dir() / "curated_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Curate: %d totali (+ %d nuovi)", len(merged), added)
    return {"ok": True, **meta}
