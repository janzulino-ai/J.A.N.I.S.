"""Adapter Telegram Bot API — polling + invio."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from backend.config import settings
from backend.core.channels.models import InboundMessage

logger = logging.getLogger("JANIS.Telegram")

_poll_task: asyncio.Task | None = None
_bot_username: str = ""


def _api_base() -> str:
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return ""
    return f"https://api.telegram.org/bot{token}"


def _offset_path() -> Path:
    p = Path(settings.MEMORY_DIR) / "channels"
    p.mkdir(parents=True, exist_ok=True)
    return p / "telegram_offset.json"


def _load_offset() -> int:
    f = _offset_path()
    if not f.exists():
        return 0
    try:
        return int(json.loads(f.read_text(encoding="utf-8")).get("offset", 0))
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    _offset_path().write_text(json.dumps({"offset": offset}), encoding="utf-8")


def telegram_status() -> dict:
    return {
        "configured": bool((settings.TELEGRAM_BOT_TOKEN or "").strip()),
        "polling": settings.TELEGRAM_POLLING and bool(_poll_task and not _poll_task.done()),
        "bot_username": _bot_username or None,
        "allowed": settings.TELEGRAM_ALLOWED_CHAT_IDS or "(tutti se vuoto)",
    }


async def _fetch_bot_username() -> None:
    global _bot_username
    base = _api_base()
    if not base:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{base}/getMe")
            data = r.json()
            if data.get("ok"):
                _bot_username = (data.get("result") or {}).get("username") or ""
    except Exception as e:
        logger.warning("getMe Telegram fallito: %s", e)


def _is_mentioned(text: str, entities: list | None) -> bool:
    if not settings.TELEGRAM_GROUP_REQUIRE_MENTION:
        return True
    uname = (_bot_username or settings.TELEGRAM_BOT_USERNAME or "").lstrip("@").lower()
    if uname and f"@{uname}" in (text or "").lower():
        return True
    for ent in entities or []:
        if ent.get("type") == "mention":
            off = ent.get("offset", 0)
            length = ent.get("length", 0)
            mention = (text or "")[off : off + length].lower()
            if uname and mention == f"@{uname}":
                return True
    return False


def _parse_update(update: dict) -> InboundMessage | None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text:
        return None
    chat = msg.get("chat") or {}
    user = msg.get("from") or {}
    chat_id = str(chat.get("id", ""))
    user_id = str(user.get("id", ""))
    is_group = chat.get("type") in ("group", "supergroup")
    mentioned = _is_mentioned(text, msg.get("entities"))
    name = " ".join(
        x for x in [user.get("first_name"), user.get("last_name")] if x
    ).strip() or user.get("username") or user_id
    return InboundMessage(
        channel="telegram",
        chat_id=chat_id,
        user_id=user_id,
        text=text,
        is_group=is_group,
        mentioned=mentioned,
        sender_name=name,
        raw=update,
    )


async def send_telegram_message(chat_id: str, text: str) -> tuple[bool, str]:
    base = _api_base()
    if not base:
        return False, "TELEGRAM_BOT_TOKEN non configurato"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{base}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096]},
            )
            data = r.json()
            if data.get("ok"):
                return True, "ok"
            return False, str(data.get("description") or data)
    except Exception as e:
        return False, str(e)


async def _poll_loop() -> None:
    base = _api_base()
    if not base:
        return
    await _fetch_bot_username()
    logger.info("Telegram polling avviato (bot @%s)", _bot_username or "?")
    offset = _load_offset()
    from backend.core.channels.manager import channel_manager

    while True:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(
                    f"{base}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                data = r.json()
                if not data.get("ok"):
                    logger.warning("getUpdates Telegram: %s", data)
                    await asyncio.sleep(5)
                    continue
                for upd in data.get("result") or []:
                    uid = upd.get("update_id", 0)
                    if uid >= offset:
                        offset = uid + 1
                        _save_offset(offset)
                    inbound = _parse_update(upd)
                    if not inbound:
                        continue
                    reply = await channel_manager.handle_inbound(inbound)
                    if reply:
                        await send_telegram_message(inbound.chat_id, reply)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Telegram poll errore: %s", e)
            await asyncio.sleep(5)


async def start_telegram_polling() -> None:
    global _poll_task
    if not settings.CHANNELS_ENABLED:
        return
    if not (settings.TELEGRAM_BOT_TOKEN or "").strip():
        return
    if not settings.TELEGRAM_POLLING:
        return
    if _poll_task and not _poll_task.done():
        return
    _poll_task = asyncio.create_task(_poll_loop(), name="janis-telegram-poll")


async def stop_telegram_polling() -> None:
    global _poll_task
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    _poll_task = None
