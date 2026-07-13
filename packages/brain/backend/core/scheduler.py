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

    prompt = (job.get("prompt") or "").strip()
    if not prompt:
        return
    logger.info("Scheduler job %s", job.get("id"))
    try:
        reply = await process_message(f"[Scheduler {job.get('id')}]\n{prompt}", stream_final=False)
        ch = (job.get("channel") or "").strip()
        cid = (job.get("chat_id") or "").strip()
        if ch and cid and reply:
            await channel_manager.send(OutboundMessage(channel=ch, chat_id=cid, text=reply[:3500]))
    except Exception:
        logger.exception("Job scheduler fallito")


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
