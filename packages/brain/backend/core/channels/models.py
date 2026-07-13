"""Modelli messaggi canali."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    channel: str
    chat_id: str
    user_id: str
    text: str
    is_group: bool = False
    mentioned: bool = True
    sender_name: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    text: str
