"""Indice cartelle — scansione media locale e integrazione memoria JANIS."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from backend.config import settings
from backend.core.security import validate_scan_path

VIDEO_EXTENSIONS = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".flv", ".mpg", ".mpeg", ".ts",
})

YEAR_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")

CATEGORY_EXTENSIONS: dict[str, frozenset[str]] = {
    "movies": VIDEO_EXTENSIONS,
}


def _index_dir() -> str:
    base = Path(settings.JANIS_PROJECT_DIR) / "data" / "index"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def index_file(category: str) -> str:
    return os.path.join(_index_dir(), f"{category}.json")


def default_scan_path(category: str) -> str:
    if category == "movies":
        return os.path.abspath(os.path.expanduser(settings.JANIS_MOVIES_PATH))
    return os.path.abspath(os.path.expanduser(settings.JANIS_WORKSPACE))


def parse_year_from_name(name: str) -> int | None:
    m = YEAR_RE.search(name)
    return int(m.group(0)) if m else None


def scan_directory(path: str, category: str = "movies") -> dict:
    """Scansiona ricorsivamente una cartella autorizzata."""
    resolved = validate_scan_path(path, must_exist=True)
    if not os.path.isdir(resolved):
        raise NotADirectoryError(f"Non è una directory: {path}")

    extensions = CATEGORY_EXTENSIONS.get(category, VIDEO_EXTENSIONS)
    items: list[dict] = []
    total_size = 0

    for root, _dirs, files in os.walk(resolved):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in extensions:
                continue
            full = os.path.join(root, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            year = parse_year_from_name(name)
            items.append({
                "name": name,
                "path": full,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "year": year,
                "extension": ext,
            })
            total_size += stat.st_size

    items.sort(key=lambda x: x["name"].lower())
    by_year: dict[str, int] = {}
    by_ext: dict[str, int] = {}
    for item in items:
        y = str(item["year"]) if item["year"] else "sconosciuto"
        by_year[y] = by_year.get(y, 0) + 1
        ext = item["extension"]
        by_ext[ext] = by_ext.get(ext, 0) + 1

    return {
        "category": category,
        "path": resolved,
        "scanned_at": datetime.now().isoformat(),
        "count": len(items),
        "total_size_bytes": total_size,
        "items": items,
        "clusters": {
            "by_year": by_year,
            "extensions": by_ext,
        },
    }


def save_index(data: dict) -> None:
    category = data.get("category", "movies")
    with open(index_file(category), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_index(category: str = "movies") -> dict | None:
    path = index_file(category)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_index_stats(category: str = "movies") -> dict:
    data = load_index(category)
    if not data:
        return {
            "category": category,
            "count": 0,
            "scanned_at": None,
            "path": default_scan_path(category),
            "total_size_bytes": 0,
        }
    return {
        "category": category,
        "count": data.get("count", 0),
        "scanned_at": data.get("scanned_at"),
        "path": data.get("path"),
        "total_size_bytes": data.get("total_size_bytes", 0),
        "clusters": data.get("clusters", {}),
    }


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def _build_summary_text(data: dict) -> str:
    count = data.get("count", 0)
    path = data.get("path", "?")
    scanned = (data.get("scanned_at") or "")[:19]
    size = _format_size(data.get("total_size_bytes", 0))
    by_year = data.get("clusters", {}).get("by_year", {})
    year_parts = [
        f"{y}×{n}" for y, n in sorted(by_year.items(), key=lambda x: (x[0] == "sconosciuto", x[0]))
    ][:8]
    year_line = ", ".join(year_parts) if year_parts else "—"
    sample = [i["name"] for i in data.get("items", [])[:12]]
    sample_line = "; ".join(sample) if sample else "—"
    return (
        f"Biblioteca film locale: {count} file video in {path} "
        f"({size}, scansione {scanned}). "
        f"Distribuzione anni: {year_line}. "
        f"Esempi: {sample_line}"
    )


def _build_year_cluster_memories(data: dict) -> list[str]:
    """Memorie aggregate per anno (max 5 cluster con almeno 2 titoli)."""
    by_year: dict[str, list[str]] = {}
    for item in data.get("items", []):
        y = str(item["year"]) if item.get("year") else "sconosciuto"
        by_year.setdefault(y, []).append(item["name"])

    texts: list[str] = []
    for year, names in sorted(by_year.items(), key=lambda x: (x[0] == "sconosciuto", x[0])):
        if len(names) < 2:
            continue
        shown = names[:20]
        extra = len(names) - len(shown)
        suffix = f" (+{extra} altri)" if extra > 0 else ""
        label = f"Film {year}" if year != "sconosciuto" else "Film (anno sconosciuto)"
        texts.append(f"{label}: {', '.join(shown)}{suffix}")
        if len(texts) >= 5:
            break
    return texts


def sync_index_to_memory(data: dict) -> int:
    """Scrive/aggiorna memorie JANIS dall'indice (cluster, non un nodo per file)."""
    from backend.core.tools.memory_tool import _load, _save, _normalize_tags

    entries = _load()
    category = data.get("category", "movies")
    base_tags = _normalize_tags([category, "media", "folder-index"])

    texts = [_build_summary_text(data)] + _build_year_cluster_memories(data)
    updated = 0
    prefix = f"[indice-{category}]"

    for text in texts:
        found = None
        for e in reversed(entries):
            if e.get("text", "").startswith(prefix) and text.split(":")[0] in e.get("text", ""):
                found = e
                break
        if not found:
            for e in reversed(entries):
                if e.get("text", "").startswith(prefix) and "Biblioteca" in text and "Biblioteca" in e.get("text", ""):
                    found = e
                    break

        if found:
            found["text"] = f"{prefix} {text}"
            found["tags"] = _normalize_tags(list(set(found.get("tags", []) + base_tags)))
            found["timestamp"] = datetime.now().isoformat()
            found["source"] = "janis"
        else:
            entries.append({
                "id": str(uuid.uuid4()),
                "text": f"{prefix} {text}",
                "tags": base_tags,
                "source": "janis",
                "timestamp": datetime.now().isoformat(),
            })
        updated += 1

    _save(entries)
    return updated


def search_index(query: str, category: str = "movies", limit: int = 15) -> list[dict]:
    data = load_index(category)
    if not data:
        return []
    q = (query or "").strip().lower()
    if not q:
        return data.get("items", [])[:limit]

    scored: list[tuple[int, dict]] = []
    for item in data.get("items", []):
        name = item.get("name", "").lower()
        path = item.get("path", "").lower()
        score = 0
        if q in name:
            score += 3
        if q in path:
            score += 1
        if item.get("year") and str(item["year"]) == q:
            score += 2
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    return [item for _, item in scored[:limit]]


def get_context_for_brain(user_text: str) -> str | None:
    """Restituisce riassunto indice se la richiesta riguarda film/media."""
    keywords = (
        "film", "movie", "movies", "cinema", "video", "mkv", "mp4",
        "biblioteca", "collezione", "titoli", "guardare", "streaming locale",
    )
    lower = (user_text or "").lower()
    if not any(k in lower for k in keywords):
        return None

    stats = get_index_stats("movies")
    data = load_index("movies")
    if not data or stats["count"] == 0:
        return (
            "=== INDICE FILM LOCALE ===\n"
            f"Nessuna scansione effettuata. Cartella predefinita: {default_scan_path('movies')}\n"
            "Usa scan_folder per indicizzare i film."
        )

    matches = search_index(user_text, "movies", limit=8)
    match_lines = "\n".join(f"- {m['name']} ({m.get('year') or '?'})" for m in matches) if matches else "—"

    return (
        "=== INDICE FILM LOCALE (scansione cartelle) ===\n"
        f"{_build_summary_text(data)}\n"
        f"Corrispondenze probabili:\n{match_lines}\n"
        "Per dettagli usa lo strumento search_folder_index o scan_folder."
    )


def run_scan(path: str | None = None, category: str = "movies") -> dict:
    target = path or default_scan_path(category)
    data = scan_directory(target, category)
    save_index(data)
    memories = sync_index_to_memory(data)
    return {
        "ok": True,
        "category": category,
        "path": data["path"],
        "count": data["count"],
        "total_size_bytes": data["total_size_bytes"],
        "scanned_at": data["scanned_at"],
        "memories_updated": memories,
        "clusters": data.get("clusters", {}),
    }
