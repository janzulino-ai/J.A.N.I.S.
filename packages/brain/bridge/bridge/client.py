#!/usr/bin/env python3
"""JANIS Fleet — client nodo headless (hello + heartbeat + command Fase 2)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
import sys
from urllib.parse import urlencode, urlparse, urlunparse

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("JANIS.FleetClient")

DEFAULT_HUB = "ws://127.0.0.1:8001/ws/fleet-node"
HEARTBEAT_INTERVAL_SEC = 30.0


def _build_url(hub_url: str, node_id: str, token: str) -> str:
    parsed = urlparse(hub_url)
    query = urlencode({"node_id": node_id, "token": token})
    path = parsed.path or "/ws/fleet-node"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


def _default_node_id() -> str:
    env_id = (os.environ.get("FLEET_NODE_ID") or "").strip()
    if env_id:
        return env_id.lower()
    host = socket.gethostname().lower().replace(" ", "-")
    if sys.platform == "darwin" and "mac" not in host:
        return "mac-mini"
    return host or "node"


async def _run_shell(command: str, cwd: str = "") -> dict:
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "ok": proc.returncode == 0,
            "stdout": (stdout or b"").decode(errors="replace"),
            "stderr": (stderr or b"").decode(errors="replace"),
            "exit_code": proc.returncode,
        }
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}


async def _heartbeat_loop(ws) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        await ws.send(json.dumps({"type": "heartbeat"}))


async def _recv_loop(ws) -> None:
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        mtype = (msg.get("type") or "").lower()
        if mtype in ("heartbeat_ack", "pong", "hello_ack"):
            continue
        if mtype == "command":
            req_id = msg.get("id") or ""
            command = msg.get("command") or ""
            cwd = msg.get("cwd") or ""
            logger.info("Comando Fleet [%s]: %s", req_id, command[:80])
            result = await _run_shell(command, cwd)
            await ws.send(json.dumps({
                "type": "command_result",
                "id": req_id,
                **result,
            }))


async def run_client(
    hub_url: str | None = None,
    node_id: str | None = None,
    token: str | None = None,
    capabilities: list[str] | None = None,
) -> None:
    hub = (hub_url or os.environ.get("FLEET_HUB_URL") or DEFAULT_HUB).strip()
    nid = (node_id or _default_node_id()).lower().strip()
    tok = (token if token is not None else os.environ.get("MAC_BRIDGE_TOKEN") or "").strip()
    caps = capabilities or ["terminal"]
    url = _build_url(hub, nid, tok)

    logger.info("Connessione Fleet → %s (node=%s)", hub, nid)

    while True:
        try:
            async with websockets.connect(url, ping_interval=None) as ws:
                hello = {
                    "type": "hello",
                    "node_id": nid,
                    "hostname": socket.gethostname(),
                    "os": platform.system().lower(),
                    "capabilities": caps,
                }
                await ws.send(json.dumps(hello))
                ack_raw = await asyncio.wait_for(ws.recv(), timeout=15)
                ack = json.loads(ack_raw)
                if ack.get("type") == "hello_ack":
                    logger.info("Registrato: %s", ack.get("node_id", nid))

                hb_task = asyncio.create_task(_heartbeat_loop(ws))
                try:
                    await _recv_loop(ws)
                finally:
                    hb_task.cancel()
                    try:
                        await hb_task
                    except asyncio.CancelledError:
                        pass
        except Exception as exc:
            logger.warning("Disconnesso (%s) — retry tra 5s", exc)
            await asyncio.sleep(5)


def main() -> None:
    asyncio.run(run_client())


if __name__ == "__main__":
    main()
