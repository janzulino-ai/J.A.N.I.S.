"""Tool janis_doctor (W7b)."""
from __future__ import annotations

import json

from backend.core.tools.registry import register


@register("janis_doctor")
async def janis_doctor(args: dict) -> str:
    """Health check sistema + heal opzionale. args: heal=true|false"""
    from backend.core.doctor import run_doctor

    heal = str(args.get("heal", "false")).lower() in ("1", "true", "yes", "on")
    report = await run_doctor(heal=heal)
    return json.dumps(report, ensure_ascii=False, indent=2)
