"""Registro nodi Fleet — MacBridgeManager (Fase 1–2)."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger("JANIS.Fleet")

HEARTBEAT_TIMEOUT_SEC = 90.0
COMMAND_TIMEOUT_SEC = 120.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class FleetNodeRecord:
    node_id: str
    hostname: str = ""
    os: str = ""
    capabilities: list[str] = field(default_factory=list)
    connected_at: str = ""
    last_heartbeat_mono: float = 0.0
    ws: WebSocket | None = None

    def is_online(self) -> bool:
        if not self.last_heartbeat_mono:
            return False
        return (time.monotonic() - self.last_heartbeat_mono) < HEARTBEAT_TIMEOUT_SEC

    def to_public_dict(self) -> dict:
        ago = None
        if self.last_heartbeat_mono:
            ago = round(time.monotonic() - self.last_heartbeat_mono, 1)
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "os": self.os,
            "capabilities": list(self.capabilities),
            "connected_at": self.connected_at,
            "online": self.is_online(),
            "last_heartbeat_sec_ago": ago,
        }


class MacBridgeManager:
    """Registra nodi worker connessi via WebSocket /ws/fleet-node."""

    def __init__(self) -> None:
        self._nodes: dict[str, FleetNodeRecord] = {}
        self._pending_commands: dict[str, asyncio.Future] = {}

    def resolve_command(self, req_id: str, payload: dict) -> None:
        fut = self._pending_commands.get(req_id)
        if fut and not fut.done():
            fut.set_result(payload)

    async def execute_command(
        self,
        node_id: str,
        command: str,
        *,
        cwd: str = "",
        timeout: float = COMMAND_TIMEOUT_SEC,
    ) -> dict:
        """Fase 2 — invia comando shell al nodo e attende risultato."""
        rec = self.get(node_id)
        if not rec or not rec.is_online() or not rec.ws:
            return {"ok": False, "error": f"nodo {node_id} offline o non registrato"}
        req_id = uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_commands[req_id] = fut
        sent = await self.send(node_id, {
            "type": "command",
            "id": req_id,
            "command": command,
            "cwd": cwd or "",
        })
        if not sent:
            self._pending_commands.pop(req_id, None)
            return {"ok": False, "error": "invio comando fallito"}
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result if isinstance(result, dict) else {"ok": True, "output": str(result)}
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"timeout dopo {timeout}s"}
        finally:
            self._pending_commands.pop(req_id, None)

    def list_nodes(self) -> list[dict]:
        return [n.to_public_dict() for n in self._nodes.values()]

    def fleet_status(self) -> dict:
        nodes = self.list_nodes()
        online = sum(1 for n in nodes if n.get("online"))
        return {
            "enabled": True,
            "nodes_total": len(nodes),
            "nodes_online": online,
            "nodes": nodes,
        }

    def get(self, node_id: str) -> FleetNodeRecord | None:
        return self._nodes.get(node_id.lower().strip())

    async def register(
        self,
        ws: WebSocket,
        node_id: str,
        *,
        hostname: str = "",
        os_name: str = "",
        capabilities: list[str] | None = None,
    ) -> FleetNodeRecord:
        nid = node_id.lower().strip()
        if not nid:
            raise ValueError("node_id richiesto")

        existing = self._nodes.get(nid)
        if existing and existing.ws is not ws:
            self.disconnect(nid)

        now_mono = time.monotonic()
        rec = FleetNodeRecord(
            node_id=nid,
            hostname=(hostname or nid).strip(),
            os=(os_name or "").strip(),
            capabilities=list(capabilities or []),
            connected_at=_now_iso(),
            last_heartbeat_mono=now_mono,
            ws=ws,
        )
        self._nodes[nid] = rec
        logger.info("Nodo Fleet registrato: %s (%s)", nid, rec.hostname)
        return rec

    def disconnect(self, node_id: str) -> None:
        nid = node_id.lower().strip()
        rec = self._nodes.pop(nid, None)
        if rec:
            logger.info("Nodo Fleet disconnesso: %s", nid)

    def touch_heartbeat(self, node_id: str) -> bool:
        rec = self.get(node_id)
        if not rec:
            return False
        rec.last_heartbeat_mono = time.monotonic()
        return True

    async def send(self, node_id: str, msg: dict) -> bool:
        rec = self.get(node_id)
        if not rec or not rec.ws:
            return False
        try:
            await rec.ws.send_json(msg)
            return True
        except Exception:
            self.disconnect(node_id)
            return False


fleet_manager = MacBridgeManager()
