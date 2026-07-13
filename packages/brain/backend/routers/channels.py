"""API gateway canali — webhook WhatsApp, status."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core.channels.manager import channel_manager
from backend.core.channels.models import InboundMessage

router = APIRouter()
logger = logging.getLogger("JANIS.ChannelsRouter")


def _check_bridge_token(authorization: str | None) -> None:
    expected = (settings.WHATSAPP_BRIDGE_TOKEN or "").strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token bridge mancante")
    if authorization[7:].strip() != expected:
        raise HTTPException(status_code=403, detail="Token bridge non valido")


class WhatsAppInboundBody(BaseModel):
    from_id: str | None = None
    from_: str | None = None
    chat_id: str | None = None
    text: str
    is_group: bool = False
    mentioned: bool = True
    sender_name: str = ""


@router.get("/api/channels/status")
async def channels_status():
    return channel_manager.status()


@router.post("/api/channels/whatsapp/inbound")
async def whatsapp_inbound(
    body: WhatsAppInboundBody,
    authorization: str | None = Header(default=None),
):
    _check_bridge_token(authorization)
    from backend.core.channels.whatsapp_bridge import mark_inbound

    mark_inbound()
    user = body.from_id or body.from_ or body.chat_id or ""
    chat = body.chat_id or user
    msg = InboundMessage(
        channel="whatsapp",
        chat_id=str(chat),
        user_id=str(user),
        text=body.text,
        is_group=body.is_group,
        mentioned=body.mentioned,
        sender_name=body.sender_name,
    )
    reply = await channel_manager.handle_inbound(msg)
    return {"ok": True, "reply": reply}
