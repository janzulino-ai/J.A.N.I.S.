"""Router Windows VM — pagina noVNC, API virsh, proxy WS VNC."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from backend.config import settings
from backend.core import win_vm

router = APIRouter()
logger = logging.getLogger("JANIS.Windows")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@router.get("/windows")
async def windows_page():
    page = FRONTEND_DIR / "windows.html"
    if page.exists():
        return FileResponse(page, headers={"Cache-Control": "no-store"})
    return JSONResponse({"error": "windows.html non trovato"}, status_code=404)


@router.get("/api/win-vm/vnc-config")
async def api_vnc_config():
    return {
        "host": settings.WIN_VM_VNC_HOST,
        "port": settings.WIN_VM_VNC_PORT,
        "password": settings.WIN_VM_VNC_PASS,
    }


@router.get("/api/win-vm/status")
async def api_win_vm_status():
    return await win_vm.vm_status()


@router.post("/api/win-vm/start")
async def api_win_vm_start():
    return await win_vm.vm_start()


@router.post("/api/win-vm/stop")
async def api_win_vm_stop():
    return await win_vm.vm_stop()


@router.post("/api/win-vm/reboot")
async def api_win_vm_reboot():
    return await win_vm.vm_reboot()


@router.websocket("/ws/vnc")
async def ws_vnc_proxy(websocket: WebSocket):
    """Proxy WebSocket ↔ VNC TCP (noVNC RFB)."""
    await websocket.accept()
    host = settings.WIN_VM_VNC_HOST
    port = settings.WIN_VM_VNC_PORT

    try:
        reader, writer = await asyncio.open_connection(host, port)
    except OSError as exc:
        logger.warning("VNC non raggiungibile %s:%s — %s", host, port, exc)
        await websocket.close(code=1011, reason="VNC offline")
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("ws_to_tcp chiuso", exc_info=True)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            logger.debug("tcp_to_ws chiuso", exc_info=True)

    try:
        await asyncio.gather(ws_to_tcp(), tcp_to_ws())
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
