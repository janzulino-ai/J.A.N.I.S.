"""Pannelli modulari UI — gestiti dall'LLM via WebSocket."""
from __future__ import annotations

import json
import uuid

from backend.core.tools.registry import register

PANEL_TYPES = ("chat", "terminal", "web", "app", "log", "brain")


@register("panel")
async def panel(args: dict) -> str:
    """
    Controlla i pannelli modulari del pannello di controllo JANIS.

    action: open | close | update | append | focus | list
    type: chat | terminal | web | app | log
    """
    action = (args.get("action") or "open").strip().lower()
    panel_id = (args.get("id") or args.get("panel_id") or "").strip()
    ptype = (args.get("type") or "chat").strip().lower()
    title = (args.get("title") or ptype.upper()).strip()

    if action == "list":
        return json.dumps(
            {"_panel_event": True, "action": "list"},
            ensure_ascii=False,
        )

    if action == "close":
        if not panel_id:
            return "Errore: 'id' obbligatorio per close."
        if panel_id == "brain-main":
            return "Il pannello cervello (brain-main) non può essere chiuso."
        return json.dumps(
            {"_panel_event": True, "action": "close", "id": panel_id},
            ensure_ascii=False,
        )

    if action in ("update", "append", "focus"):
        if not panel_id:
            return "Errore: 'id' obbligatorio."
        payload = {
            "_panel_event": True,
            "action": action,
            "id": panel_id,
            "type": ptype,
        }
        if args.get("content") is not None:
            payload["content"] = str(args["content"])
        if args.get("title"):
            payload["title"] = title
        if args.get("url"):
            payload["url"] = str(args["url"])
        return json.dumps(payload, ensure_ascii=False)

    # open
    if ptype not in PANEL_TYPES:
        ptype = "app"
    pid = panel_id or f"{ptype}-{uuid.uuid4().hex[:8]}"
    payload = {
        "_panel_event": True,
        "action": "open",
        "id": pid,
        "type": ptype,
        "title": title,
    }
    if args.get("url"):
        payload["url"] = str(args["url"])
    if args.get("content"):
        payload["content"] = str(args["content"])
    if args.get("command"):
        payload["command"] = str(args["command"])
    if args.get("width"):
        payload["width"] = int(args["width"])
    if args.get("height"):
        payload["height"] = int(args["height"])
    if ptype == "web" and not args.get("width"):
        payload["width"] = 640
    if ptype == "web" and not args.get("height"):
        payload["height"] = 420
    if ptype == "brain" and not args.get("width"):
        payload["width"] = 440
    if ptype == "brain" and not args.get("height"):
        payload["height"] = 360
    if ptype == "brain" and not panel_id:
        pid = "brain-main"
        payload["id"] = pid
    return json.dumps(payload, ensure_ascii=False)
