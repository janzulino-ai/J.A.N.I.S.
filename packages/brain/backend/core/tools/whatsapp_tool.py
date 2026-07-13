"""Strumento WhatsApp — invio via bridge HTTP quando configurato."""
from __future__ import annotations

from backend.core.tools.registry import register


@register("whatsapp_send")
async def whatsapp_send(args: dict) -> str:
    to = (args.get("to") or args.get("phone") or args.get("group_id") or args.get("chat_id") or "").strip()
    message = (args.get("message") or args.get("text") or "").strip()
    is_group = bool(args.get("group") or args.get("is_group") or "g.us" in to)

    if not message:
        return "Errore: 'message' obbligatorio."

    from backend.config import settings

    if not (settings.WHATSAPP_BRIDGE_URL or "").strip():
        hint = (
            "WhatsApp non collegato. Configura WHATSAPP_BRIDGE_URL e avvia bridge/whatsapp "
            "(vedi docs/CHANNELS.md)."
        )
        if is_group:
            hint += " Per i gruppi serve id chat @g.us e menzione configurata."
        return f"{hint}\nMessaggio NON inviato: {message[:200]}"

    from backend.core.channels.manager import channel_manager
    from backend.core.channels.models import OutboundMessage

    if not to:
        return "Errore: destinatario (to/chat_id) obbligatorio quando il bridge è attivo."

    ok, detail = await channel_manager.send(
        OutboundMessage(channel="whatsapp", chat_id=to, text=message)
    )
    if ok:
        return f"WhatsApp inviato a {to}."
    return f"Invio WhatsApp fallito: {detail}"
