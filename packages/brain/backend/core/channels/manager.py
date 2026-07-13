"""ChannelManager — inbound → brain → outbound."""
from __future__ import annotations

import asyncio
import logging

from backend.core.channels.models import InboundMessage, OutboundMessage
from backend.core.channels.policy import check_inbound
from backend.core.response_style import compute_tts_text

logger = logging.getLogger("JANIS.Channels")

_MAX_REPLY = 3800


class ChannelManager:
    def __init__(self) -> None:
        self._busy: set[str] = set()
        self.stats = {"inbound": 0, "replied": 0, "blocked": 0, "errors": 0}

    async def handle_inbound(self, msg: InboundMessage) -> str | None:
        """Elabora messaggio esterno con lo stesso brain della UI."""
        from backend.core.brain import process_message

        key = f"{msg.channel}:{msg.chat_id}"
        allowed, reason = check_inbound(msg)
        if not allowed:
            self.stats["blocked"] += 1
            logger.info("Canale bloccato [%s] %s: %s", msg.channel, msg.chat_id, reason)
            return None

        if key in self._busy:
            return "Sto ancora rispondendo al messaggio precedente — riprova tra poco."

        self._busy.add(key)
        self.stats["inbound"] += 1
        try:
            text = (msg.text or "").strip()
            if not text:
                return None
            prefix = f"[Canale {msg.channel}"
            if msg.sender_name:
                prefix += f" — {msg.sender_name}"
            prefix += "]\n"
            reply = await process_message(prefix + text, on_event=None, stream_final=False)
            reply = (reply or "").strip()
            if not reply:
                reply = "Non ho una risposta in questo momento."
            # Risposta chat: testo completo ma capped; TTS non usato su canali
            if len(reply) > _MAX_REPLY:
                short = compute_tts_text(reply) or reply[:400]
                reply = f"{short}\n\n(risposta abbreviata — dettagli completi nella UI JANIS)"
            self.stats["replied"] += 1
            return reply[:_MAX_REPLY]
        except Exception as e:
            self.stats["errors"] += 1
            logger.exception("Errore canale %s", msg.channel)
            return f"Errore interno JANIS: {e}"
        finally:
            self._busy.discard(key)

    async def send(self, out: OutboundMessage) -> tuple[bool, str]:
        if out.channel == "telegram":
            from backend.core.channels.telegram import send_telegram_message

            return await send_telegram_message(out.chat_id, out.text)
        if out.channel == "whatsapp":
            from backend.core.channels.whatsapp_bridge import send_whatsapp_message

            return await send_whatsapp_message(out.chat_id, out.text)
        return False, f"canale {out.channel} non supportato"

    def status(self) -> dict:
        from backend.config import settings
        from backend.core.channels.telegram import telegram_status
        from backend.core.channels.whatsapp_bridge import whatsapp_status

        return {
            "enabled": settings.CHANNELS_ENABLED,
            "stats": dict(self.stats),
            "telegram": telegram_status(),
            "whatsapp": whatsapp_status(),
        }


channel_manager = ChannelManager()
