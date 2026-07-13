"""Avvio e verifica Ollama locale."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Ollama")


async def is_ollama_online(timeout: float = 3.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def _ollama_exe() -> Path | None:
    if sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if p.is_file():
            return p
    exe = shutil.which("ollama")
    return Path(exe) if exe else None


def start_ollama_process() -> bool:
    exe = _ollama_exe()
    if not exe:
        logger.warning("Ollama non trovato — installa da https://ollama.com")
        return False
    try:
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([str(exe), "serve"], **kwargs)
        logger.info("Avvio Ollama: %s serve", exe)
        return True
    except Exception as e:
        logger.warning("Impossibile avviare Ollama: %s", e)
        return False


async def ensure_ollama_running(wait_sec: float = 20.0) -> bool:
    """Verifica Ollama; se offline prova ad avviarlo (Windows/Linux/macOS con CLI)."""
    if await is_ollama_online():
        return True
    if not start_ollama_process():
        return False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_sec
    while loop.time() < deadline:
        await asyncio.sleep(0.5)
        if await is_ollama_online():
            logger.info("Ollama online")
            return True
    logger.warning("Ollama non risponde dopo %ss", wait_sec)
    return False
