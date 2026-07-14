"""Percezione — STT, visione, stato sensori."""
from __future__ import annotations

import json

from backend.core.tools.registry import register


@register("perception_status")
async def perception_status(_args: dict) -> str:
    """Stato STT locale, visione Pocket e modelli Ollama vision disponibili."""
    from backend.core.perception import build_perception_status

    return json.dumps(await build_perception_status(), ensure_ascii=False, indent=2)


@register("describe_vision")
async def describe_vision(args: dict) -> str:
    """
    Analizza ultima immagine Pocket o path file (base64 opzionale).
    args: device_id (opz.) | path | image_base64
    """
    from backend.core.perception import describe_image

    return await describe_image(
        device_id=args.get("device_id"),
        path=args.get("path"),
        image_base64=args.get("image_base64"),
        context=args.get("context") or "",
    )
