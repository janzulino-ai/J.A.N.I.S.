"""Apre URL nel browser di sistema — ideale per YouTube, streaming, SPA pesanti."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from backend.core.open_url import normalize_url, open_system_url
from backend.core.tools.registry import register

_EXTERNAL_HOSTS = re.compile(
    r"(^|\.)("
    r"youtube\.com|youtu\.be|netflix\.com|twitch\.tv|spotify\.com|"
    r"facebook\.com|instagram\.com|twitter\.com|x\.com|tiktok\.com"
    r")$",
    re.I,
)


def is_external_only(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return bool(_EXTERNAL_HOSTS.search(host))
    except Exception:
        return False


@register("open_browser")
async def open_browser(args: dict) -> str:
    """
    Apre un sito nel browser di Windows (Edge/Chrome predefinito).
    Usa per qualsiasi sito web — JANIS non embedda pagine nel pannello.

    args:
      - url (required): indirizzo completo o dominio (es. youtube.com)
      - title: ignorato (solo compatibilità)
    """
    try:
        url = normalize_url(args.get("url") or args.get("site") or "")
    except ValueError as e:
        return f"Errore: {e}"

    open_system_url(url)
    host = (urlparse(url).hostname or "Browser").replace("www.", "")
    return json.dumps(
        {
            "_panel_event": True,
            "action": "browser_opened",
            "url": url,
            "title": host,
        },
        ensure_ascii=False,
    )
