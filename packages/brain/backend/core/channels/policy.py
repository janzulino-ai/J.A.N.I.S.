"""Policy sicurezza canali — allowlist, menzione gruppi."""
from __future__ import annotations

from backend.config import settings
from backend.core.channels.models import InboundMessage


def _parse_id_list(raw: str) -> set[str]:
    return {x.strip() for x in (raw or "").split(",") if x.strip()}


def check_inbound(msg: InboundMessage) -> tuple[bool, str]:
    """Ritorna (allowed, reason)."""
    if not settings.CHANNELS_ENABLED:
        return False, "canali disabilitati"

    if msg.channel == "telegram":
        allowed = _parse_id_list(settings.TELEGRAM_ALLOWED_CHAT_IDS)
        if allowed and msg.chat_id not in allowed and msg.user_id not in allowed:
            return False, "chat non in allowlist"
        if msg.is_group and settings.TELEGRAM_GROUP_REQUIRE_MENTION and not msg.mentioned:
            return False, "menzione richiesta in gruppo"
        return True, "ok"

    if msg.channel == "whatsapp":
        allowed = _parse_id_list(settings.WHATSAPP_ALLOWED_FROM)
        if allowed:
            norm = msg.user_id.replace("@c.us", "").replace("@g.us", "")
            if msg.user_id not in allowed and norm not in allowed and msg.chat_id not in allowed:
                return False, "numero/gruppo non in allowlist"
        if msg.is_group and settings.WHATSAPP_GROUP_REQUIRE_MENTION and not msg.mentioned:
            return False, "menzione richiesta in gruppo"
        return True, "ok"

    return False, f"canale sconosciuto: {msg.channel}"
