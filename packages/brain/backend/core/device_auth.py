"""Auth leggera per device mobili (Pocket) — header X-JANIS-Token."""

from __future__ import annotations

from fastapi import Header, HTTPException

from backend.config import settings


def require_device_token(x_janis_token: str | None = Header(default=None)) -> None:
    expected = (settings.JANIS_DEVICE_TOKEN or "").strip()
    if not expected:
        return
    if not x_janis_token or x_janis_token.strip() != expected:
        raise HTTPException(status_code=401, detail="Token device non valido")
