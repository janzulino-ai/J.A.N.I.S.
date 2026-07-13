"""AgentHost — terminali OS visibili (modello Cursor), 1 sessione per topic."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("JANIS.AgentHost")

CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0


@dataclass
class AgentSession:
    agent_id: str
    topic: str
    command: str
    cwd: str
    pid: int
    use_wsl: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    title: str = ""

    def to_dict(self) -> dict:
        alive = _pid_alive(self.pid)
        return {
            "agent_id": self.agent_id,
            "topic": self.topic,
            "command": self.command,
            "cwd": self.cwd,
            "pid": self.pid,
            "use_wsl": self.use_wsl,
            "title": self.title,
            "created_at": self.created_at,
            "alive": alive,
        }


_sessions: dict[str, AgentSession] = {}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_wt() -> str | None:
    return shutil.which("wt.exe") or shutil.which("wt")


def spawn_visible(
    command: str,
    *,
    topic: str = "default",
    cwd: str = "",
    use_wsl: bool = False,
    keep_open: bool = True,
) -> AgentSession:
    """Apre terminale visibile. Su Windows preferisce Windows Terminal."""
    agent_id = uuid.uuid4().hex[:8]
    title = f"JANIS::{topic}"
    workdir = cwd or os.getcwd()

    if use_wsl:
        inner = command.replace('"', '\\"')
        if keep_open:
            shell_cmd = f'{inner}; exec bash'
        else:
            shell_cmd = inner
        base = ["wsl.exe", "-e", "bash", "-lc", shell_cmd]
    elif sys.platform == "win32":
        if keep_open:
            ps = f'{command}; if ($LASTEXITCODE -ne 0) {{ Write-Host "exit: $LASTEXITCODE" -ForegroundColor Red }}; Read-Host "Premi Invio per chiudere"'
        else:
            ps = command
        base = ["powershell.exe", "-NoExit", "-Command", ps] if keep_open else ["powershell.exe", "-Command", ps]
    else:
        base = ["bash", "-lc", command if not keep_open else f"{command}; read -p 'Invio per chiudere'"]

    wt = _find_wt()
    if wt and sys.platform == "win32":
        if use_wsl:
            args = [wt, "new-tab", "--title", title, "wsl.exe", "-e", "bash", "-lc", shell_cmd]
        else:
            args = [wt, "new-tab", "--title", title] + base
        proc = subprocess.Popen(args, cwd=workdir, creationflags=CREATE_NEW_CONSOLE)
    elif sys.platform == "win32":
        cmd_line = " ".join(f'"{a}"' if " " in a else a for a in base)
        proc = subprocess.Popen(f'start "{title}" {cmd_line}', shell=True, cwd=workdir)
    else:
        proc = subprocess.Popen(base, cwd=workdir)

    session = AgentSession(
        agent_id=agent_id,
        topic=topic,
        command=command,
        cwd=workdir,
        pid=proc.pid,
        use_wsl=use_wsl,
        title=title,
    )
    _sessions[agent_id] = session
    logger.info("AgentHost spawn %s topic=%s pid=%s", agent_id, topic, session.pid)
    return session


def list_sessions() -> list[dict]:
    dead = [k for k, s in _sessions.items() if not _pid_alive(s.pid)]
    for k in dead:
        _sessions.pop(k, None)
    return [s.to_dict() for s in _sessions.values()]


def get_session(agent_id: str) -> dict | None:
    s = _sessions.get(agent_id)
    if not s:
        return None
    if not _pid_alive(s.pid):
        _sessions.pop(agent_id, None)
        return None
    return s.to_dict()


def kill_session(agent_id: str) -> bool:
    s = _sessions.pop(agent_id, None)
    if not s:
        return False
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(s.pid), "/F"], capture_output=True, timeout=10)
            return True
        except Exception:
            return False
    try:
        os.kill(s.pid, 9)
        return True
    except OSError:
        return False


def is_heavy_command(command: str) -> bool:
    """Comandi che meritano terminale visibile."""
    c = (command or "").lower().strip()
    if not c:
        return False
    heavy = (
        "git ", "npm ", "pip ", "pytest", "docker ", "build", "deploy",
        "cargo ", "make ", "cmake", "ssh ", "wsl ", "curl ", "winget ",
        "autodev", "compile", "install", "uvicorn", "python -m",
    )
    return any(h in c for h in heavy)
