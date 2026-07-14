"""Loop autosufficienza — osserva gap, reflect, propone (non applica senza policy)."""

from __future__ import annotations

import logging

from backend.config import settings

logger = logging.getLogger("JANIS.Autonomy")


async def run_autonomy_tick() -> dict:
    """Un ciclo: health + gap aperti → reflect dry-run o run se gap high."""
    from backend.core.capability_gaps import list_gaps
    from backend.core.ollama_service import ensure_ollama_running
    from backend.core.reflect import list_proposals, run_reflection

    report: dict = {"ok": True, "actions": []}

    ollama_ok = await ensure_ollama_running()
    if not ollama_ok:
        report["actions"].append("ollama_offline")
        return report

    gaps = list_gaps(status="open")
    high = [g for g in gaps if (g.get("severity") or "").lower() == "high"]
    open_code = [p for p in list_proposals("open") if p.get("type") == "code"]

    if not high and not open_code:
        report["actions"].append("nothing_todo")
        if not settings.AUTONOMY_REFLECT_ENABLED:
            report["actions"].append("reflect_disabled")
        elif settings.LAB_ENABLED:
            pass  # salta reflect, continua verso lab sotto
        else:
            return report

    if high or open_code:
        if not settings.AUTONOMY_REFLECT_ENABLED:
            report["actions"].append("reflect_disabled")
        else:
            result = await run_reflection(dry_run=False, max_msgs=40)
            report["reflect"] = {
                "summary": result.get("summary", ""),
                "proposals": len(result.get("proposals") or []),
                "preferences": len(result.get("preferences") or []),
            }
            report["actions"].append("reflect_run")

            if settings.AUTONOMY_AUTODEV_ENABLED and high:
                report["actions"].append("autodev_skipped_needs_approval")

    if settings.LAB_ENABLED:
        try:
            from backend.core.llm_lab.train import run_full_cycle

            lab_result = await run_full_cycle(harvest_first=True)
            report["lab"] = {
                "action": lab_result.get("action"),
                "steps": len(lab_result.get("steps") or []),
            }
            report["actions"].append(f"lab_{lab_result.get('action', 'cycle')}")
        except Exception:
            logger.exception("Lab cycle in autonomy")

    try:
        from pathlib import Path
        import json
        from datetime import datetime, timezone
        from backend.config import settings

        p = Path(settings.JANIS_PROJECT_DIR) / "data" / "autonomy_last.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(),
            "report": report,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return report
