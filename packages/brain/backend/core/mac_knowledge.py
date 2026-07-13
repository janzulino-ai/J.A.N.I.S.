"""Conoscenza progetti Mac — scansione SSH + arricchimento Ollama."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

from backend.config import settings
from backend.core.ssh_client import mac_node_config, run_mac_ssh

logger = logging.getLogger("JANIS.MacKnowledge")

STACK_MARKERS = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "Makefile",
    "Dockerfile",
)

_REMOTE_SCAN_SCRIPT = r"""
bash -lc '
ROOT="${SCAN_ROOT:-$HOME/Documents}"
ROOT="${ROOT/#\~/$HOME}"
printf "["
first=1
shopt -s nullglob 2>/dev/null || true
for d in "$ROOT"/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  case "$name" in .*|node_modules) continue ;; esac
  path="${d%/}"
  has_git=0; [ -d "$path/.git" ] && has_git=1
  has_cursor=0; [ -d "$path/.cursor" ] && has_cursor=1
  readme=""
  for r in README.md README README.txt readme.md; do
    [ -f "$path/$r" ] && readme="$r" && break
  done
  stacks=""
  for m in package.json requirements.txt pyproject.toml setup.py Cargo.toml go.mod Gemfile composer.json pom.xml build.gradle Makefile Dockerfile; do
    [ -f "$path/$m" ] && stacks="${stacks}${m},"
  done
  stacks="${stacks%,}"
  [ "$first" -eq 0 ] && printf ","
  first=0
  printf "{\"name\":\"%s\",\"path\":\"%s\",\"has_git\":%s,\"has_cursor\":%s,\"readme\":\"%s\",\"stack_files\":\"%s\"}" \
    "$name" "$path" "$has_git" "$has_cursor" "$readme" "$stacks"
done
printf "]\n"
'
"""


def _state_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "knowledge" / "mac_projects_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"projects": {}, "last_scan": None, "last_enriched": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"projects": {}, "last_scan": None, "last_enriched": None}


def save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_mac_knowledge_status() -> dict:
    state = load_state()
    projects = state.get("projects") or {}
    cfg = mac_node_config()
    return {
        "scan_root": settings.MAC_SSH_SCAN_ROOT,
        "mac_ssh_enabled": cfg["enabled"],
        "mac_host": cfg.get("host"),
        "last_scan": state.get("last_scan"),
        "last_enriched": state.get("last_enriched"),
        "project_count": len(projects),
        "projects": projects,
    }


def _parse_scan_json(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("Output SSH non contiene JSON array")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("JSON progetti non valido")
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        path = str(item.get("path") or "").strip()
        if not name or not path:
            continue
        stack_raw = str(item.get("stack_files") or "")
        stacks = [s.strip() for s in stack_raw.split(",") if s.strip()]
        out.append({
            "name": name,
            "path": path,
            "has_git": bool(item.get("has_git")),
            "has_cursor": bool(item.get("has_cursor")),
            "readme": str(item.get("readme") or ""),
            "stack_files": stacks,
        })
    return out


async def scan_mac_projects(scan_root: str | None = None) -> dict:
    """Scansiona progetti Cursor sul Mac via SSH (non interattivo)."""
    cfg = mac_node_config()
    if not cfg["enabled"]:
        return {"ok": False, "error": "Mac SSH disabilitato", "projects": []}

    root = (scan_root or settings.MAC_SSH_SCAN_ROOT or "~/Documents").strip()
    safe_root = root.replace("'", "'\\''")
    cmd = f"SCAN_ROOT='{safe_root}'; {_REMOTE_SCAN_SCRIPT}"
    code, out, err = await run_mac_ssh(cmd)
    if code != 0:
        detail = (err or out or "SSH fallito").strip()[:500]
        return {"ok": False, "error": detail, "projects": [], "exit_code": code}

    try:
        projects = _parse_scan_json(out)
    except (json.JSONDecodeError, ValueError) as e:
        return {"ok": False, "error": f"Parse scan: {e}", "raw": out[:800], "projects": []}

    state = load_state()
    state["last_scan"] = datetime.now().isoformat()
    for p in projects:
        state.setdefault("projects", {})[p["path"]] = {
            **p,
            "scanned_at": state["last_scan"],
        }
    save_state(state)
    return {"ok": True, "scan_root": root, "projects": projects, "count": len(projects)}


def _parse_enrichment_json(raw: str) -> dict:
    raw = (raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("Risposta Ollama non JSON")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON non valido")
    return data


async def enrich_projects_with_ollama(projects: list[dict]) -> dict:
    from backend.core.llm_router import chat as llm_chat

    payload = []
    for p in projects[:20]:
        payload.append({
            "name": p.get("name"),
            "path": p.get("path"),
            "git": p.get("has_git"),
            "cursor": p.get("has_cursor"),
            "readme": p.get("readme"),
            "stack": p.get("stack_files") or [],
        })

    prompt = (
        "Sei il cervello di JANIS. Analizza questi progetti Cursor sul Mac Mini "
        "e crea conoscenza strutturata (vault Obsidian): stack, scopo, relazioni.\n\n"
        f"Progetti:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Rispondi SOLO con JSON valido:\n"
        '{"summary":"2-4 frasi panoramica fleet Mac",'
        '"projects":[{"name":"...","purpose":"...","stack":"...","tags":["..."],"related":["..."]}]}\n'
        "Massimo 12 progetti. Italiano. Niente markdown fuori dal JSON."
    )
    raw, provider = await llm_chat([{"role": "user", "content": prompt}])
    logger.info("Arricchimento Mac Ollama (%s) — %d progetti", provider, len(projects))
    data = _parse_enrichment_json(raw)
    data.setdefault("summary", "")
    data.setdefault("projects", [])
    return data


def sync_mac_enrichment_to_memory(projects: list[dict], enrichment: dict) -> list[dict]:
    from backend.core.tools.memory_tool import _load, _normalize_tags, _save

    entries = _load()
    created: list[dict] = []
    base_tags = _normalize_tags(["mac", "cursor-project", "fleet", "knowledge-mac"])

    def upsert(text: str, tags: list[str], folder: str | None = None) -> dict:
        tag_set = _normalize_tags(tags + base_tags)
        prefix = text[:48]
        for e in reversed(entries):
            if e.get("text", "").startswith(prefix[:40]):
                e["text"] = text
                e["tags"] = tag_set
                e["timestamp"] = datetime.now().isoformat()
                e["source"] = "janis"
                if folder:
                    e["folder"] = folder
                return e
        entry = {
            "id": str(uuid.uuid4()),
            "text": text,
            "tags": tag_set,
            "source": "janis",
            "timestamp": datetime.now().isoformat(),
        }
        if folder:
            entry["folder"] = folder
        entries.append(entry)
        created.append(entry)
        return entry

    summary = (enrichment.get("summary") or "").strip()
    if summary:
        upsert(f"[Mac Fleet] {summary}", ["mac-fleet", "summary"])

    by_name = {p.get("name"): p for p in projects}
    for item in enrichment.get("projects") or []:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        purpose = (item.get("purpose") or "").strip()
        stack_raw = item.get("stack") or ""
        if isinstance(stack_raw, list):
            stack = ", ".join(str(s) for s in stack_raw)
        else:
            stack = str(stack_raw).strip()
        tags = _normalize_tags(item.get("tags") or [])
        related = item.get("related") or []
        meta = by_name.get(name) or {}
        path = meta.get("path") or name
        rel_line = f" Collegamenti: {', '.join(related[:6])}." if related else ""
        stack_line = f" Stack: {stack}." if stack else ""
        git_line = " Git." if meta.get("has_git") else ""
        text = f"[Mac/{name}] {purpose}{stack_line}{git_line}{rel_line} Path: {path}"
        upsert(text, tags + [name.lower().replace(" ", "-")], folder=path)

    for p in projects:
        if any(p.get("name") in (e.get("text") or "") for e in created):
            continue
        stacks = ", ".join(p.get("stack_files") or []) or "unknown"
        text = (
            f"[Mac/{p['name']}] Progetto in {p['path']}. "
            f"Stack hints: {stacks}."
            f"{' Git repo.' if p.get('has_git') else ''}"
            f"{' Cursor config.' if p.get('has_cursor') else ''}"
        )
        upsert(text, [p["name"].lower().replace(" ", "-"), "scanned"], folder=p["path"])

    _save(entries)
    return created


async def scan_and_learn_mac_projects(
    scan_root: str | None = None,
    *,
    learn: bool = True,
) -> dict:
    """Scansione completa + arricchimento Ollama + memoria/neuroni."""
    scan = await scan_mac_projects(scan_root=scan_root)
    if not scan.get("ok"):
        return scan

    projects = scan.get("projects") or []
    if not learn:
        return {**scan, "learned": False}

    if not projects:
        return {**scan, "learned": False, "message": "Nessun progetto trovato"}

    enrichment = await enrich_projects_with_ollama(projects)
    new_entries = sync_mac_enrichment_to_memory(projects, enrichment)
    from backend.core.knowledge_graph import node_from_memory

    nodes = [node_from_memory(e) for e in new_entries]
    state = load_state()
    state["last_enriched"] = datetime.now().isoformat()
    for p in projects:
        key = p["path"]
        prev = state.get("projects", {}).get(key) or {}
        state.setdefault("projects", {})[key] = {
            **prev,
            **p,
            "enriched_at": state["last_enriched"],
        }
    save_state(state)

    return {
        **scan,
        "learned": True,
        "summary": enrichment.get("summary"),
        "memories_created": len(new_entries),
        "nodes": nodes,
        "nodes_created": len(nodes),
        "last_enriched": state["last_enriched"],
    }


def get_context_for_brain(user_text: str | None = None) -> str | None:
    from backend.core.tools.memory_tool import (
        count_memories_by_tags,
        get_memories_by_tags,
        search_memories,
    )

    state = load_state()
    projects = state.get("projects") or {}
    mac_memory_count = count_memories_by_tags(["knowledge-mac"])

    if not projects and mac_memory_count == 0:
        return None

    lines = ["=== PROGETTI MAC (Cursor fleet) ==="]
    if state.get("last_enriched"):
        lines.append(f"Ultimo arricchimento: {state['last_enriched'][:19]}")
    if state.get("last_scan"):
        lines.append(f"Ultima scansione SSH: {state['last_scan'][:19]}")

    for path, meta in list(projects.items())[:14]:
        name = meta.get("name") or Path(path).name
        stacks = ", ".join(meta.get("stack_files") or []) or "—"
        when = (meta.get("enriched_at") or meta.get("scanned_at") or "")[:19]
        lines.append(f"- {name} ({path}): stack={stacks}, aggiornato {when}")

    fleet_mem = get_memories_by_tags(["mac-fleet"], limit=1)
    if fleet_mem:
        lines.append(f"\nSintesi fleet (memoria): {fleet_mem[0].get('text', '')[:320]}")

    mac_memories = get_memories_by_tags(["knowledge-mac"], limit=8)
    project_memories = [
        e for e in mac_memories
        if (e.get("text") or "").startswith("[Mac/") or "[Mac/" in (e.get("text") or "")
    ]
    if project_memories:
        lines.append("\nConoscenza Mac in long_term.json:")
        for entry in project_memories[:5]:
            lines.append(f"• {entry.get('text', '')[:220]}")

    if user_text:
        hits = [h for h in search_memories(user_text) if "mac" in (h.get("tags") or [])][:4]
        if hits:
            lines.append("\nMemorie Mac rilevanti alla domanda:")
            for h in hits:
                lines.append(f"• {h.get('text', '')[:220]}")

    return "\n".join(lines)
