"""Client MCP stdio — spawn server da servers.json, tools/list, tools/call."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Any

from backend.config import settings
from backend.core.mcp_bridge import load_mcp_servers

logger = logging.getLogger("JANIS.MCPClient")

_PROTOCOL = "2024-11-05"
_sessions: dict[str, "_McpSession"] = {}
_lock = asyncio.Lock()


class _McpSession:
    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.proc: asyncio.subprocess.Process | None = None
        self._id = 0
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._tools: list[dict] | None = None
        self._stderr_buf = ""

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def start(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        cmd = _resolve_command(self.command) or shutil.which(self.command) or self.command
        env = {**os.environ, **self.env}
        # Assicura ~/.local/bin nel PATH del subprocess
        local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        self.proc = await asyncio.create_subprocess_exec(
            cmd,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=8 * 1024 * 1024,
        )
        self._reader_task = asyncio.create_task(self._read_loop(), name=f"mcp-read-{self.name}")
        await self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "janis-brain", "version": "2.0.0"},
            },
        )
        await self._notify("notifications/initialized", {})
        logger.info("MCP session avviata: %s", self.name)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=3)
            except (asyncio.TimeoutError, ProcessLookupError):
                self.proc.kill()
        self.proc = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("MCP session closed"))
        self._pending.clear()

    async def _read_loop(self) -> None:
        assert self.proc and self.proc.stdout
        buf = b""
        try:
            while True:
                chunk = await self.proc.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    sep = buf.find(b"\r\n\r\n")
                    if sep < 0:
                        break
                    header = buf[:sep].decode("utf-8", errors="replace")
                    buf = buf[sep + 4 :]
                    length = 0
                    for line in header.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            length = int(line.split(":", 1)[1].strip())
                    if length <= 0 or len(buf) < length:
                        buf = header.encode() + b"\r\n\r\n" + buf
                        break
                    body = buf[:length]
                    buf = buf[length:]
                    try:
                        msg = json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    mid = msg.get("id")
                    if mid is not None and mid in self._pending:
                        fut = self._pending.pop(mid)
                        if "error" in msg:
                            fut.set_exception(RuntimeError(json.dumps(msg["error"])))
                        else:
                            fut.set_result(msg.get("result"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MCP read loop %s", self.name)

    async def _write(self, payload: dict) -> None:
        assert self.proc and self.proc.stdin
        data = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + data)
        await self.proc.stdin.drain()

    async def _notify(self, method: str, params: dict) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict, timeout: float = 60.0) -> Any:
        if not self.proc or self.proc.returncode is not None:
            await self.start()
        rid = self._next_id()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[rid] = fut
        await self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except Exception:
            self._pending.pop(rid, None)
            raise

    async def list_tools(self, *, force: bool = False) -> list[dict]:
        if self._tools is not None and not force:
            return self._tools
        result = await self._request("tools/list", {})
        tools = (result or {}).get("tools") or []
        self._tools = tools if isinstance(tools, list) else []
        return self._tools

    async def call_tool(self, name: str, arguments: dict | None = None, timeout: float = 120.0) -> str:
        result = await self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout=timeout,
        )
        if not isinstance(result, dict):
            return str(result)
        if result.get("isError"):
            return f"MCP error: {result}"
        parts: list[str] = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)


def mcp_enabled() -> bool:
    return bool(getattr(settings, "MCP_ENABLED", True))


def _server_by_name(name: str) -> dict | None:
    for s in load_mcp_servers():
        if (s.get("name") or "").strip() == name:
            return s
    return None


async def get_session(server_name: str) -> _McpSession:
    async with _lock:
        if server_name in _sessions:
            sess = _sessions[server_name]
            if sess.proc and sess.proc.returncode is None:
                return sess
            await sess.close()
            _sessions.pop(server_name, None)
        conf = _server_by_name(server_name)
        if not conf:
            raise ValueError(f"Server MCP '{server_name}' non in servers.json")
        cmd = (conf.get("command") or "").strip()
        if not cmd:
            raise ValueError(f"Server MCP '{server_name}' senza command")
        args = conf.get("args") or []
        if not isinstance(args, list):
            args = []
        env = conf.get("env") if isinstance(conf.get("env"), dict) else {}
        sess = _McpSession(server_name, cmd, [str(a) for a in args], env)
        await sess.start()
        _sessions[server_name] = sess
        return sess


async def close_all_sessions() -> None:
    async with _lock:
        for name, sess in list(_sessions.items()):
            await sess.close()
            _sessions.pop(name, None)


def _resolve_command(cmd: str) -> str | None:
    if not cmd:
        return None
    found = shutil.which(cmd)
    if found:
        return found
    if os.path.isfile(cmd):
        return cmd
    home = os.path.expanduser("~")
    for candidate in (
        os.path.join(home, ".local", "bin", cmd),
        os.path.join(home, "janis-venv", "bin", cmd),
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


async def mcp_server_status() -> list[dict[str, Any]]:
    """Stato server dichiarati: online se command trovato; tool list se sessione attiva."""
    out: list[dict[str, Any]] = []
    for s in load_mcp_servers():
        name = (s.get("name") or "?").strip()
        cmd = (s.get("command") or "").strip()
        resolved = _resolve_command(cmd)
        entry: dict[str, Any] = {
            "name": name,
            "command": cmd,
            "args": s.get("args") or [],
            "command_found": bool(resolved),
            "session_active": name in _sessions
            and _sessions[name].proc is not None
            and _sessions[name].proc.returncode is None,
            "tools": [],
            "error": None,
        }
        if entry["session_active"]:
            try:
                entry["tools"] = [
                    t.get("name") for t in await _sessions[name].list_tools() if isinstance(t, dict)
                ]
            except Exception as e:
                entry["error"] = str(e)[:200]
        out.append(entry)
    return out


async def call_mcp_tool(
    server: str,
    tool: str,
    arguments: dict | None = None,
    *,
    timeout: float | None = None,
) -> str:
    if not mcp_enabled():
        raise RuntimeError("MCP_ENABLED=false")
    t = timeout if timeout is not None else float(getattr(settings, "MCP_CALL_TIMEOUT_SEC", 120))
    sess = await get_session(server)
    return await sess.call_tool(tool, arguments or {}, timeout=t)
