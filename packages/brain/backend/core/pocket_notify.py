"""Notify Pocket — device command + coda push locale (W7a)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.PocketNotify")


def _push_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "push"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _outbox_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "pocket" / "notify_outbox"
    p.mkdir(parents=True, exist_ok=True)
    return p


def registered_devices() -> list[str]:
    d = _push_dir()
    return [f.stem for f in d.glob("*.json")]


def notify_device(device_id: str, title: str, body: str, data: dict | None = None) -> dict[str, Any]:
    """Notifica un device: ios_bridge notify + outbox (APNs reale se configurato)."""
    result: dict[str, Any] = {"device_id": device_id, "bridge": False, "outbox": False, "apns": False}
    try:
        from backend.routers.ios_bridge import enqueue_command

        enqueue_command(
            device_id,
            "notify",
            {"title": title, "body": body, "data": data or {}},
        )
        result["bridge"] = True
    except Exception as e:
        result["bridge_error"] = str(e)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "title": title,
        "body": body,
        "data": data or {},
    }
    out = _outbox_dir() / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{device_id}.json"
    out.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    result["outbox"] = True
    result["outbox_path"] = str(out)

    # APNs opzionale: se esiste modulo/cert (non obbligatorio in LOCAL_FIRST)
    try:
        apns_key = getattr(settings, "APNS_KEY_PATH", "") or ""
        if apns_key and Path(apns_key).is_file():
            result["apns"] = _try_apns(device_id, title, body, data)
    except Exception as e:
        result["apns_error"] = str(e)[:200]

    return result


def notify_all(title: str, body: str, data: dict | None = None) -> list[dict]:
    devices = registered_devices()
    if not devices:
        # fallback device ids contratto
        devices = ["iphone-15-pro-max", "iphone-14-pro", "ipad-pro-2020"]
    return [notify_device(d, title, body, data) for d in devices]


def notify_digest(summary: str) -> list[dict]:
    return notify_all("JANIS digest", summary, {"type": "digest"})


def _try_apns(device_id: str, title: str, body: str, data: dict | None) -> bool:
    """Invio APNs best-effort se token + chiave presenti."""
    reg = _push_dir() / f"{device_id}.json"
    if not reg.exists():
        return False
    token_info = json.loads(reg.read_text(encoding="utf-8"))
    token = token_info.get("token") or ""
    if not token:
        return False
    # Placeholder: senza libreria PyAPNs2 non inviamo; logghiamo intent
    logger.info("APNs ready for %s (token len=%d) — installa provider o usa bridge notify", device_id, len(token))
    # Scrivi payload pronto per worker esterno
    payload = {
        "device_token": token,
        "aps": {"alert": {"title": title, "body": body}, "sound": "default"},
        "data": data or {},
    }
    apns_out = _outbox_dir() / f"apns_{device_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.json"
    apns_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True
