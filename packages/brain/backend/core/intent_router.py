"""Intent router — suggerisce tool / shortcut per process_message e heartbeat (W6d)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class IntentHint:
    intent: str
    tools: list[str]
    note: str
    confidence: float = 0.6


_URL_RE = re.compile(r"https?://\S+", re.I)
_DOC_EXT = (".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".odt")
_IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
_VID_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi")


def classify_intent(text: str) -> IntentHint:
    t = (text or "").strip()
    lower = t.lower()

    # Multi-step autonomy
    if any(k in lower for k in ("in autonomia", "lavora da sola", "heartbeat", "crea ticket", "metti in coda")):
        return IntentHint("autonomy_ticket", ["ticket_create", "heartbeat_run", "board_status"], "Crea ticket e lascia heartbeat", 0.85)

    # URL / social → reach
    if _URL_RE.search(t) or any(
        k in lower for k in ("youtube", "reddit", "twitter", "x.com", "cosa dicono", "agent-reach", "fetch url")
    ):
        return IntentHint("reach", ["reach", "research"], "Fetch piattaforma / URL (solo lettura)", 0.8)

    # Deep research
    if any(
        k in lower
        for k in (
            "ricerca",
            "research",
            "con fonti",
            "citazioni",
            "report su",
            "approfondisci",
            "searx",
        )
    ):
        return IntentHint("research", ["research", "reach", "remember"], "Research con citazioni → LTM", 0.75)

    # Documents
    if any(ext in lower for ext in _DOC_EXT) or any(
        k in lower for k in ("pdf", "docx", "powerpoint", "excel", "documento", "docling", "officecli")
    ):
        if any(k in lower for k in ("modifica", "edita", "aggiungi", "scrivi in")):
            return IntentHint("office_edit", ["office_edit", "doc_read"], "Edit Office via OfficeCLI", 0.8)
        return IntentHint("doc_read", ["doc_read", "office_edit"], "Leggi documento Docling", 0.8)

    # Vision
    if any(ext in lower for ext in _IMG_EXT + _VID_EXT) or any(
        k in lower for k in ("descrivi foto", "descrivi immagine", "cosa vedi", "vision", "screenshot", "frame")
    ):
        return IntentHint("vision", ["describe_vision", "perception_status"], "Visione locale / Pocket", 0.8)

    # Code graph
    if any(
        k in lower
        for k in (
            "nel codice",
            "codebase",
            "dove è definito",
            "simbolo",
            "indicizza repo",
            "code_search",
            "grafo codice",
        )
    ):
        return IntentHint("code", ["code_search", "code_symbol", "code_index", "cursor_code"], "Grafo codice poi Cursor", 0.8)

    # Media gen
    if any(k in lower for k in ("genera immagine", "genera video", "image_gen", "comfy", "txt2img", "crea un'immagine")):
        if "video" in lower:
            return IntentHint("video_gen", ["video_gen", "media_status"], "ComfyUI video", 0.75)
        return IntentHint("image_gen", ["image_gen", "media_status"], "ComfyUI locale", 0.75)

    # Device / mobile
    if any(k in lower for k in ("mobile-mcp", "tap su", "ui iphone", "automazione ios", "fleet_execute")):
        return IntentHint("device", ["mobile_ui", "fleet_execute", "mac_ssh"], "Device UI / fleet", 0.7)

    # Doctor
    if any(k in lower for k in ("janis doctor", "health check", "self-heal", "stato sidecar")):
        return IntentHint("doctor", ["janis_doctor", "mcp_status", "board_status"], "Doctor sistema", 0.9)

    # Memory default-ish
    if any(k in lower for k in ("ricorda che", "metti in memoria", "cosa ricordi")):
        return IntentHint("memory", ["remember", "recall", "semantic_recall"], "Memoria persona", 0.7)

    return IntentHint("general", [], "", 0.3)


def intent_system_block(hint: IntentHint) -> str:
    if not hint.tools:
        return ""
    tools = ", ".join(hint.tools)
    return (
        f"\n\nINTENT ROUTER: intent={hint.intent} (conf={hint.confidence:.2f}).\n"
        f"Preferisci tool: {tools}.\n"
        f"Nota: {hint.note}"
    )


def extract_path_arg(text: str) -> str | None:
    # Windows / POSIX paths
    m = re.search(r'["\']([^"\']+\.(?:pdf|docx|pptx|xlsx|png|jpe?g|webp|mp4|mov))["\']', text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"([A-Za-z]:\\[^\s]+?\.(?:pdf|docx|pptx|xlsx|png|jpe?g|webp|mp4|mov))", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(/[^\s]+?\.(?:pdf|docx|pptx|xlsx|png|jpe?g|webp|mp4|mov))", text, re.I)
    if m:
        return m.group(1)
    return None


async def maybe_fast_path(text: str) -> str | None:
    """Esegue shortcut sicuri senza LLM (solo read/status)."""
    hint = classify_intent(text)
    lower = text.lower().strip()

    if hint.intent == "doctor" and any(k in lower for k in ("doctor", "health")):
        from backend.core.doctor import run_doctor
        import json

        return json.dumps(await run_doctor(heal="heal" in lower or "ripara" in lower), ensure_ascii=False, indent=2)

    if hint.intent == "doc_read":
        path = extract_path_arg(text)
        if path and Path(path).is_file():
            from backend.core.tools.doc_tool import doc_read

            return await doc_read({"path": path})

    if hint.intent == "vision":
        path = extract_path_arg(text)
        if path and Path(path).is_file():
            from backend.core.tools.perception_tool import describe_vision

            return await describe_vision({"path": path})

    return None


def board_goal_context() -> str:
    try:
        from backend.core.orchestrator.board import board_status, get_autonomy_level, load_goals

        g = load_goals()
        st = board_status()
        goals = g.get("goals") or []
        open_g = [x.get("title") for x in goals if x.get("status") == "open"][:5]
        return (
            f"\n\nORCHESTRATOR: autonomy={get_autonomy_level()} · "
            f"tickets={st.get('tickets')} · mission={g.get('mission')}\n"
            f"Goals aperti: {', '.join(open_g) or '—'}"
        )
    except Exception:
        return ""
