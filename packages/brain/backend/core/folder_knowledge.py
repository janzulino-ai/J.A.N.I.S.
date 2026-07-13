"""Conoscenza da cartelle — Ollama arricchisce memoria e neuroni (stile Obsidian)."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from backend.config import settings
from backend.core.security import scan_roots, validate_scan_path

logger = logging.getLogger("JANIS.FolderKnowledge")

TEXT_EXTENSIONS = frozenset({
    ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".html", ".csv", ".log", ".rst",
})
MEDIA_EXTENSIONS = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".mp3", ".flac", ".wav",
    ".jpg", ".jpeg", ".png", ".gif", ".pdf",
})
SKIP_DIR_NAMES = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "$recycle.bin", "system volume information",
})

MAX_FILES = 180
MAX_SNIPPET_CHARS = 1200
MAX_SNIPPETS = 18
MAX_MEDIA_NAMES = 40
MAX_DIRS = 35


def _state_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "knowledge" / "folders_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"folders": {}, "last_enriched": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"folders": {}, "last_enriched": None}


def save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_scan_roots(roots: list[str]) -> list[str]:
    """Salva radici cartelle in .env e settings."""
    unique: list[str] = []
    seen: set[str] = set()
    for raw in roots:
        if not raw or not str(raw).strip():
            continue
        try:
            path = os.path.abspath(os.path.expanduser(str(raw).strip()))
        except OSError:
            continue
        key = os.path.normcase(path)
        if key in seen:
            continue
        if os.path.isdir(path):
            seen.add(key)
            unique.append(path)

    value = ",".join(unique)
    env_path = Path(settings.JANIS_PROJECT_DIR) / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        if line.startswith("JANIS_SCAN_ROOTS="):
            out.append(f"JANIS_SCAN_ROOTS={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"JANIS_SCAN_ROOTS={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    object.__setattr__(settings, "JANIS_SCAN_ROOTS", value)
    return unique


def add_knowledge_folder_path(path: str) -> str:
    """Aggiunge una cartella alle radici conoscenza."""
    from backend.core.security import validate_local_folder

    resolved = validate_local_folder(path)
    roots = scan_roots()
    if not any(os.path.normcase(r) == os.path.normcase(resolved) for r in roots):
        roots.append(resolved)
    persist_scan_roots(roots)
    return resolved


def get_knowledge_status() -> dict:
    state = load_state()
    folders = state.get("folders") or {}
    total_clusters = sum(int(v.get("clusters", 0)) for v in folders.values())
    return {
        "last_enriched": state.get("last_enriched"),
        "folder_count": len(folders),
        "clusters": total_clusters,
        "folders": folders,
        "scan_roots": scan_roots(),
    }


def _read_snippet(path: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit).strip()
    except OSError:
        return ""


def collect_inventory(folder_path: str) -> dict:
    """Inventario leggero: struttura, snippet testuali, nomi media."""
    resolved = validate_scan_path(folder_path, must_exist=True)
    if not os.path.isdir(resolved):
        raise NotADirectoryError(folder_path)

    dirs: list[dict] = []
    snippets: list[dict] = []
    media_names: list[str] = []
    file_count = 0

    for root, dirnames, filenames in os.walk(resolved):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIR_NAMES and not d.startswith(".")]
        rel = os.path.relpath(root, resolved)
        if rel == ".":
            rel = ""
        if len(dirs) < MAX_DIRS:
            dirs.append({"path": rel or ".", "files": len(filenames), "subdirs": len(dirnames)})

        for name in filenames:
            if file_count >= MAX_FILES:
                break
            file_count += 1
            ext = os.path.splitext(name)[1].lower()
            full = os.path.join(root, name)
            rel_file = os.path.join(rel, name) if rel else name

            if ext in TEXT_EXTENSIONS and len(snippets) < MAX_SNIPPETS:
                body = _read_snippet(full)
                if body:
                    snippets.append({"file": rel_file, "preview": body[:400]})
            elif ext in MEDIA_EXTENSIONS and len(media_names) < MAX_MEDIA_NAMES:
                media_names.append(rel_file)

        if file_count >= MAX_FILES:
            break

    return {
        "path": resolved,
        "file_count": file_count,
        "dirs": dirs,
        "snippets": snippets,
        "media_names": media_names,
    }


def _parse_enrichment_json(raw: str) -> dict:
    raw = (raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("Risposta Ollama non JSON")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON non valido")
    return data


async def enrich_inventory_with_ollama(folder_path: str, inventory: dict) -> dict:
    from backend.core.llm_router import chat as llm_chat

    payload = {
        "dirs": inventory.get("dirs", [])[:25],
        "snippets": inventory.get("snippets", [])[:12],
        "media_names": inventory.get("media_names", [])[:20],
        "file_count": inventory.get("file_count", 0),
    }
    prompt = (
        f"Sei il cervello di JANIS. Analizza la cartella '{folder_path}' e crea conoscenza "
        "strutturata come un vault Obsidian: cluster tematici, collegamenti, tag — NON un elenco file.\n\n"
        f"Inventario:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Rispondi SOLO con JSON valido:\n"
        '{"area":"titolo breve area","summary":"2-4 frasi sintesi",'
        '"clusters":[{"title":"...","insight":"...","tags":["..."],"related":["..."]}]}\n'
        "Massimo 6 cluster. Italiano. Niente markdown fuori dal JSON."
    )
    raw, provider = await llm_chat([{"role": "user", "content": prompt}])
    logger.info("Arricchimento Ollama (%s) per %s", provider, folder_path)
    data = _parse_enrichment_json(raw)
    data.setdefault("area", os.path.basename(folder_path.rstrip("\\/")) or "Cartella")
    data.setdefault("summary", "")
    data.setdefault("clusters", [])
    return data


def sync_enrichment_to_memory(folder_path: str, enrichment: dict) -> list[dict]:
    """Scrive memorie cluster → alimentano i neuroni del second brain."""
    from backend.core.tools.memory_tool import _load, _normalize_tags, _save

    entries = _load()
    created: list[dict] = []
    base_tags = _normalize_tags(["cartella", "knowledge-folder", "obsidian"])
    area = enrichment.get("area") or Path(folder_path).name
    prefix = f"[{area}]"

    def upsert(text: str, tags: list[str]) -> dict:
        tag_set = _normalize_tags(tags + base_tags)
        for e in reversed(entries):
            if e.get("text", "").startswith(prefix) and text[:40] in e.get("text", ""):
                e["text"] = text
                e["tags"] = tag_set
                e["timestamp"] = datetime.now().isoformat()
                e["source"] = "janis"
                e["folder"] = folder_path
                return e
        entry = {
            "id": str(uuid.uuid4()),
            "text": text,
            "tags": tag_set,
            "source": "janis",
            "timestamp": datetime.now().isoformat(),
            "folder": folder_path,
        }
        entries.append(entry)
        created.append(entry)
        return entry

    summary = (enrichment.get("summary") or "").strip()
    if summary:
        upsert(f"{prefix} {summary}", [area.lower(), "summary"])

    for cluster in enrichment.get("clusters") or []:
        title = (cluster.get("title") or "Cluster").strip()
        insight = (cluster.get("insight") or "").strip()
        tags = _normalize_tags(cluster.get("tags") or [])
        related = cluster.get("related") or []
        rel_line = f" Collegamenti: {', '.join(related[:6])}." if related else ""
        text = f"{prefix} {title}: {insight}{rel_line}"
        upsert(text, tags + [title.lower().replace(" ", "-")])

    _save(entries)
    return created


async def enrich_folder(folder_path: str) -> dict:
    inventory = collect_inventory(folder_path)
    enrichment = await enrich_inventory_with_ollama(folder_path, inventory)
    new_entries = sync_enrichment_to_memory(folder_path, enrichment)
    from backend.core.knowledge_graph import node_from_memory

    nodes = [node_from_memory(e) for e in new_entries]
    state = load_state()
    state.setdefault("folders", {})[folder_path] = {
        "enriched_at": datetime.now().isoformat(),
        "area": enrichment.get("area"),
        "clusters": len(enrichment.get("clusters") or []),
        "file_count": inventory.get("file_count", 0),
    }
    state["last_enriched"] = datetime.now().isoformat()
    save_state(state)
    return {
        "path": folder_path,
        "area": enrichment.get("area"),
        "clusters": len(enrichment.get("clusters") or []),
        "memories_created": len(new_entries),
        "nodes": nodes,
        "file_count": inventory.get("file_count", 0),
    }


async def enrich_all_folders() -> dict:
    """Arricchisce tutte le cartelle selezionate in Impostazioni."""
    roots = scan_roots()
    if not roots:
        return {"ok": False, "error": "Nessuna cartella selezionata", "nodes": []}

    state = load_state()
    all_nodes: list[dict] = []
    results: list[dict] = []

    for root in roots:
        try:
            r = await enrich_folder(root)
            results.append(r)
            all_nodes.extend(r.get("nodes") or [])
            state["folders"][root] = {
                "enriched_at": datetime.now().isoformat(),
                "area": r.get("area"),
                "clusters": r.get("clusters", 0),
                "file_count": r.get("file_count", 0),
            }
        except Exception as e:
            logger.exception("Arricchimento fallito: %s", root)
            results.append({"path": root, "error": str(e)})

    state["last_enriched"] = datetime.now().isoformat()
    save_state(state)

    return {
        "ok": True,
        "folders": len(results),
        "nodes": all_nodes,
        "nodes_created": len(all_nodes),
        "results": results,
        "last_enriched": state["last_enriched"],
    }


def get_context_for_brain(user_text: str | None = None) -> str | None:
    """Contesto leggero dalle cartelle conosciute (sempre disponibile se c'è memoria)."""
    state = load_state()
    folders = state.get("folders") or {}
    if not folders:
        roots = scan_roots()
        if not roots:
            return None
        return (
            "=== CARTELLE DA CONOSCERE ===\n"
            f"Cartelle selezionate ({len(roots)}): " + ", ".join(roots[:8]) + "\n"
            "Non ancora arricchite con Ollama — salva le cartelle in Impostazioni per avviare l'apprendimento."
        )

    lines = ["=== CONOSCENZA DA CARTELLE (vault locale) ==="]
    for path, meta in list(folders.items())[:12]:
        area = meta.get("area") or os.path.basename(path)
        when = (meta.get("enriched_at") or "")[:19]
        lines.append(
            f"- {area} ({path}): {meta.get('clusters', 0)} cluster, "
            f"{meta.get('file_count', 0)} file analizzati, aggiornato {when}"
        )

    if user_text:
        from backend.core.tools.memory_tool import search_memories
        hits = search_memories(user_text)
        tagged = [h for h in hits if "knowledge-folder" in (h.get("tags") or [])][:5]
        if tagged:
            lines.append("\nMemorie rilevanti:")
            for h in tagged:
                lines.append(f"• {h.get('text', '')[:220]}")

    return "\n".join(lines)
