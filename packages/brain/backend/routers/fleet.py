"""Router Fleet — registro nodi worker (Fase 1)."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.config import settings
from backend.core.fleet.manager import fleet_manager

router = APIRouter()
logger = logging.getLogger("JANIS.FleetRouter")


def _valid_token(token: str) -> bool:
    expected = (settings.MAC_BRIDGE_TOKEN or "").strip()
    if not expected:
        return True
    return (token or "").strip() == expected


@router.get("/api/fleet/nodes")
async def fleet_nodes():
    return fleet_manager.fleet_status()


@router.websocket("/ws/fleet-node")
async def ws_fleet_node(
    websocket: WebSocket,
    token: str = Query(default=""),
    node_id: str = Query(default=""),
):
    await websocket.accept()

    if not _valid_token(token):
        await websocket.send_json({"type": "error", "message": "Token Fleet non valido"})
        await websocket.close(code=4401)
        return

    registered_id = (node_id or "").lower().strip()
    if not registered_id:
        await websocket.send_json({"type": "error", "message": "node_id richiesto (query o hello)"})
        await websocket.close(code=4400)
        return

    try:
        rec = await fleet_manager.register(websocket, registered_id)
        await websocket.send_json({
            "type": "hello_ack",
            "node_id": rec.node_id,
            "coordinator": settings.FLEET_COORDINATOR,
            "message": "Registrato sul coordinatore Fleet",
        })

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "JSON non valido"})
                continue

            msg_type = (msg.get("type") or "").lower().strip()

            if msg_type == "hello":
                hid = (msg.get("node_id") or registered_id).lower().strip()
                if hid and hid != registered_id:
                    fleet_manager.disconnect(registered_id)
                    registered_id = hid
                rec = await fleet_manager.register(
                    websocket,
                    registered_id,
                    hostname=str(msg.get("hostname") or ""),
                    os_name=str(msg.get("os") or msg.get("platform") or ""),
                    capabilities=msg.get("capabilities") if isinstance(msg.get("capabilities"), list) else [],
                )
                await websocket.send_json({
                    "type": "hello_ack",
                    "node_id": rec.node_id,
                    "coordinator": settings.FLEET_COORDINATOR,
                })
                continue

            if msg_type in ("heartbeat", "ping"):
                fleet_manager.touch_heartbeat(registered_id)
                await websocket.send_json({
                    "type": "heartbeat_ack" if msg_type == "heartbeat" else "pong",
                    "node_id": registered_id,
                })
                continue

            if msg_type == "command_result":
                req_id = str(msg.get("id") or "")
                fleet_manager.resolve_command(req_id, {
                    "ok": bool(msg.get("ok", True)),
                    "stdout": str(msg.get("stdout") or msg.get("output") or ""),
                    "stderr": str(msg.get("stderr") or ""),
                    "exit_code": msg.get("exit_code"),
                    "error": msg.get("error"),
                })
                continue

            await websocket.send_json({
                "type": "error",
                "message": f"Tipo messaggio non supportato: {msg_type or '?'}",
            })

    except WebSocketDisconnect:
        fleet_manager.disconnect(registered_id)
    except Exception:
        logger.exception("Errore WS fleet-node %s", registered_id)
        fleet_manager.disconnect(registered_id)
        raise
