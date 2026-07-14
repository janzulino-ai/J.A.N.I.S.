"""Client SSH verso nodi JANIS (Mac Mini, …)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.SSH")

_HARDWARE_CACHE: dict | None = None
_MAC_PING_CACHE: dict | None = None
_MAC_PING_AT: float = 0.0
_MAC_PING_TTL_SEC = 30.0


def _load_hardware() -> dict:
    global _HARDWARE_CACHE
    if _HARDWARE_CACHE is not None:
        return _HARDWARE_CACHE
    path = Path(settings.JANIS_PROJECT_DIR) / "data" / "hardware.json"
    if path.exists():
        try:
            _HARDWARE_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return _HARDWARE_CACHE
        except Exception as e:
            logger.warning("hardware.json: %s", e)
    _HARDWARE_CACHE = {}
    return _HARDWARE_CACHE


def mac_node_config() -> dict:
    hw = _load_hardware()
    node = (hw.get("nodes") or {}).get("mac-mini") or {}
    host = (settings.MAC_SSH_HOST or node.get("hostname") or node.get("lan_ip") or "").strip()
    user = (settings.MAC_SSH_USER or node.get("ssh_user") or "janzu").strip()
    key = (settings.MAC_SSH_KEY or "").strip()
    if not key:
        default_key = Path.home() / ".ssh" / "id_ed25519"
        if default_key.exists():
            key = str(default_key)
    return {
        "enabled": bool(settings.MAC_SSH_ENABLED and host),
        "host": host,
        "user": user,
        "key": key,
        "label": node.get("label") or "Mac Mini",
    }


def _ssh_base_args(cfg: dict) -> list[str]:
    args = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={settings.MAC_SSH_TIMEOUT_SEC}",
        "-o", "StrictHostKeyChecking=accept-new",
    ]
    if cfg.get("key") and os.path.isfile(cfg["key"]):
        args.extend(["-i", cfg["key"]])
    target = f"{cfg['user']}@{cfg['host']}"
    args.append(target)
    return args


async def run_mac_ssh(command: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Esegue comando sul Mac via SSH. Ritorna (exit_code, stdout, stderr)."""
    cfg = mac_node_config()
    if not cfg["enabled"]:
        raise RuntimeError(
            "Mac SSH non configurato. Imposta MAC_SSH_ENABLED=1 e MAC_SSH_HOST in .env"
        )

    remote_cmd = command
    if cwd:
        safe_cwd = cwd.replace("'", "'\\''")
        remote_cmd = f"cd '{safe_cwd}' && {command}"

    cmd = _ssh_base_args(cfg) + [remote_cmd]
    logger.info("Mac SSH: %s@%s → %s", cfg["user"], cfg["host"], command[:120])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.TOOL_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError(f"Timeout SSH Mac ({settings.TOOL_TIMEOUT_SEC}s)")

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return proc.returncode or 0, stdout, stderr


async def mac_ssh_ping() -> dict:
    """Verifica connettività SSH al Mac (cache 30s)."""
    import time
    global _MAC_PING_CACHE, _MAC_PING_AT
    now = time.time()
    if _MAC_PING_CACHE is not None and now - _MAC_PING_AT < _MAC_PING_TTL_SEC:
        return _MAC_PING_CACHE

    cfg = mac_node_config()
    if not cfg["enabled"]:
        _MAC_PING_CACHE = {**cfg, "online": False, "error": "disabled"}
        _MAC_PING_AT = now
        return _MAC_PING_CACHE
    try:
        code, out, err = await run_mac_ssh("echo JANIS_OK && uname -s && sw_vers -productVersion")
        ok = code == 0 and "JANIS_OK" in out
        _MAC_PING_CACHE = {
            **cfg,
            "online": ok,
            "exit_code": code,
            "info": (out or err).strip()[:500],
        }
    except Exception as e:
        _MAC_PING_CACHE = {**cfg, "online": False, "error": str(e)}
    _MAC_PING_AT = now
    return _MAC_PING_CACHE
