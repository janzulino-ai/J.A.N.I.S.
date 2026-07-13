"""Bridge HTTP WhatsApp — riceve da bridge Node, invia via bridge."""
from __future__ import annotations

import logging

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.WhatsAppBridge")

_last_bridge_ping: str | None = None


def whatsapp_status() -> dict:
    url = (settings.WHATSAPP_BRIDGE_URL or "").strip()
    return {
        "configured": bool(url),
        "bridge_url": url or None,
        "allowed": settings.WHATSAPP_ALLOWED_FROM or "(tutti se vuoto)",
        "last_inbound": _last_bridge_ping,
    }


def _bridge_headers() -> dict:
    tok = (settings.WHATSAPP_BRIDGE_TOKEN or "").strip()
    if tok:
        return {"Authorization": f"Bearer {tok}"}
    return {}


async def send_whatsapp_message(to: str, text: str) -> tuple[bool, str]:
    base = (settings.WHATSAPP_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        return False, "WHATSAPP_BRIDGE_URL non configurato — vedi docs/CHANNELS.md"
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                f"{base}/send",
                json={"to": to, "message": text[:4000]},
                headers=_bridge_headers(),
            )
            if r.status_code == 200:
                return True, "ok"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


def mark_inbound() -> None:
    global _last_bridge_ping
    from datetime import datetime, timezone

    _last_bridge_ping = datetime.now(timezone.utc).isoformat()
