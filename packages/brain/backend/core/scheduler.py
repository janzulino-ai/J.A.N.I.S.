"""Scheduler locale — briefing/cron (pattern OpenClaw heartbeat)."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.Scheduler")

_task: asyncio.Task | None = None
_autonomy_task: asyncio.Task | None = None
_TICK_SEC = 60.0


def _jobs_path() -> Path:
    p = Path(settings.MEMORY_DIR) / "scheduler_jobs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def default_jobs() -> list[dict]:
    return [
        {
            "id": "morning-status",
            "enabled": True,
            "hour": 8,
            "minute": 0,
            "prompt": "Breve briefing: stato sistema, nodi fleet, proposte aperte. Max 5 righe.",
            "channel": "",
            "chat_id": "",
        },
        {
            "id": "weekly-tech-scout",
            "enabled": True,
            "hour": 6,
            "minute": 0,
            "weekday": 0,
            "action": "scout_discover",
            "prompt": "[Tech Scout] Discovery watchlist + gap. Report max 10 righe.",
            "channel": "",
            "chat_id": "",
        },
        {
            "id": "nightly-lab-harvest",
            "enabled": True,
            "hour": 3,
            "minute": 0,
            "action": "lab_harvest",
            "channel": "",
            "chat_id": "",
        },
        {
            "id": "weekly-lab-train",
            "enabled": False,
            "hour": 4,
            "minute": 0,
            "weekday": 6,
            "action": "lab_train",
            "channel": "",
            "chat_id": "",
        },
    ]


def load_jobs() -> list[dict]:
    f = _jobs_path()
    if not f.exists():
        jobs = default_jobs()
        f.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        return jobs
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return default_jobs()


def save_jobs(jobs: list[dict]) -> None:
    _jobs_path().write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run_job(job: dict) -> None:
    from backend.core.brain import process_message
    from backend.core.channels.manager import channel_manager
    from backend.core.channels.models import OutboundMessage

    action = (job.get("action") or "").strip()
    if action == "scout_discover":
        from backend.core.tech_scout.discover import discover_all
        from backend.core.tech_scout.classifier import classify_candidate
        logger.info("Scheduler scout_discover")
        try:
            result = await discover_all(sources=["watchlist", "github"])
            for c in result.get("candidates") or []:
                classify_candidate(c)
            prompt = (job.get("prompt") or "") + f"\nTrovati {result.get('count', 0)} candidati."
            reply = await process_message(prompt, stream_final=False)
        except Exception:
            logger.exception("Scout job fallito")
            return
    elif action == "lab_harvest":
        from backend.core.llm_lab.harvest import harvest_chats
        from backend.core.llm_lab.curate import curate_dataset
        logger.info("Scheduler lab_harvest")
        try:
            h = await harvest_chats()
            c = await curate_dataset()
            reply = await process_message(
                f"[LLM Lab] Harvest {h.get('examples', 0)} esempi. Curated totale: {c.get('total', 0)}.",
                stream_final=False,
            )
        except Exception:
            logger.exception("Lab harvest job fallito")
            return
    elif action == "lab_train":
        from backend.core.llm_lab.train import run_full_cycle
        logger.info("Scheduler lab_train")
        try:
            result = await run_full_cycle(harvest_first=True)
            reply = await process_message(
                f"[LLM Lab] Cycle action={result.get('action')}. "
                f"Steps: {len(result.get('steps') or [])}.",
                stream_final=False,
            )
        except Exception:
            logger.exception("Lab train job fallito")
            return
    else:
        prompt = (job.get("prompt") or "").strip()
        if not prompt:
            return
        logger.info("Scheduler job %s", job.get("id"))
        try:
            reply = await process_message(f"[Scheduler {job.get('id')}]\n{prompt}", stream_final=False)
        except Exception:
            logger.exception("Job scheduler fallito")
            return

    ch = (job.get("channel") or "").strip()
    cid = (job.get("chat_id") or "").strip()
    if ch and cid and reply:
        await channel_manager.send(OutboundMessage(channel=ch, chat_id=cid, text=reply[:3500]))


async def _autonomy_loop() -> None:
    interval = max(60, int(settings.AUTONOMY_INTERVAL_MIN) * 60)
    while True:
        try:
            await asyncio.sleep(interval)
            if settings.AUTONOMY_ENABLED:
                from backend.core.autonomy_loop import run_autonomy_tick
                report = await run_autonomy_tick()
                logger.info("Autonomy tick: %s", report.get("actions"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Autonomy loop")


async def _tick_loop() -> None:
    last_run: dict[str, str] = {}
    while True:
        try:
            now = datetime.now(timezone.utc)
            key_min = now.strftime("%Y-%m-%d-%H:%M")
            for job in load_jobs():
                if not job.get("enabled"):
                    continue
                jid = job.get("id") or "?"
                if last_run.get(jid) == key_min:
                    continue
                if now.hour == int(job.get("hour", -1)) and now.minute == int(job.get("minute", -1)):
                    wd = job.get("weekday")
                    if wd is not None and now.weekday() != int(wd):
                        continue
                    last_run[jid] = key_min
                    await _run_job(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler tick")
        await asyncio.sleep(_TICK_SEC)


async def start_scheduler() -> None:
    global _task, _autonomy_task
    if not settings.SCHEDULER_ENABLED:
        return
    if _task and not _task.done():
        return
    load_jobs()
    _task = asyncio.create_task(_tick_loop(), name="janis-scheduler")
    if settings.AUTONOMY_ENABLED:
        _autonomy_task = asyncio.create_task(_autonomy_loop(), name="janis-autonomy")
    logger.info("Scheduler avviato (autonomy=%s)", settings.AUTONOMY_ENABLED)


def scheduler_status() -> dict:
    jobs = load_jobs()
    return {
        "enabled": settings.SCHEDULER_ENABLED,
        "running": _task is not None and not _task.done(),
        "autonomy_enabled": settings.AUTONOMY_ENABLED,
        "autonomy_running": _autonomy_task is not None and not _autonomy_task.done(),
        "job_count": len(jobs),
        "enabled_jobs": sum(1 for j in jobs if j.get("enabled")),
        "jobs": [
            {
                "id": j.get("id"),
                "enabled": j.get("enabled"),
                "hour": j.get("hour"),
                "minute": j.get("minute"),
                "weekday": j.get("weekday"),
                "action": j.get("action") or "prompt",
            }
            for j in jobs
        ],
    }


async def stop_scheduler() -> None:
    global _task, _autonomy_task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    if _autonomy_task and not _autonomy_task.done():
        _autonomy_task.cancel()
        try:
            await _autonomy_task
        except asyncio.CancelledError:
            pass
    _autonomy_task = None
