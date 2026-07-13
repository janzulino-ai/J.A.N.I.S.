from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import logging

from backend.core.brain import process_message, check_ollama, clear_session, init_session, get_session_history
from backend.core.chat_store import get_history, list_sessions, current_session_id
from backend.core.orchestrator.cost_router import cost_router

router = APIRouter()
logger = logging.getLogger("JANIS.Chat")


class ChatRequest(BaseModel):
    text: str


class FolderScanRequest(BaseModel):
    category: str = Field(default="movies")
    path: str | None = None


class MacScanRequest(BaseModel):
    scan_root: str | None = Field(default=None, description="Directory remota, default ~/Documents")
    learn: bool = Field(default=True, description="Arricchimento Ollama + memoria")


@router.get("/api/status")
async def status():
    ollama = await check_ollama()
    from backend.routers.websocket import manager
    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    from backend.core.ssh_client import mac_ssh_ping

    mac = await mac_ssh_ping()
    from backend.core.fleet.manager import fleet_manager
    from backend.core import presence
    from backend.routers.stt import SUPPORTED_FORMATS, _probe_engines

    stt = _probe_engines()

    return {
        "service": "JANIS",
        "version": "2.0.0",
        "runtime_api": True,
        "paid_mode": rt.paid_mode,
        "reasoning_provider": rt.reasoning_provider,
        "ollama": ollama,
        "mac_node": mac,
        "fleet": fleet_manager.fleet_status(),
        "presence": presence.get_presence(),
        "stt": {
            "ready": stt.get("ready"),
            "engine": stt.get("engine"),
            "formats": list(SUPPORTED_FORMATS),
        },
        "pocket_api": {
            "ingest": "/api/pocket/ingest",
            "telemetry": "/api/pocket/telemetry",
            "vision": "/api/pocket/vision",
            "push_register": "/api/pocket/push/register",
            "stt": "/api/stt",
            "claim": "/api/presence/claim",
            "ios_pending": "/api/devices/ios/pending",
            "identity_verify": "/api/identity/verify",
            "emergency_sos": "/api/emergency/sos",
        },
        "orchestrator": cost_router.status(),
        "active_client": manager.active,
        "connected_clients": list(manager.connections.keys()),
        "session_messages": len(get_session_history()),
        "session_id": current_session_id(),
        "brain_version": 5,
    }




@router.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    client = (req.headers.get("x-janis-client") or "api").lower()
    if client == "cursor":
        logger.info("CHAT via API (client=cursor)")

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Testo vuoto")

    ollama = await check_ollama()
    if not ollama.get("online"):
        from backend.core.ollama_service import ensure_ollama_running
        if not await ensure_ollama_running():
            raise HTTPException(status_code=503, detail="Ollama non raggiungibile")

    async def sse():
        result = await process_message(text, on_event=None, stream_final=False)
        yield f"data: {json.dumps({'type': 'final', 'text': result}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@router.get("/api/knowledge")
async def knowledge():
    from backend.core.tools.memory_tool import get_knowledge_stats
    return get_knowledge_stats()


@router.get("/api/knowledge/graph")
async def knowledge_graph():
    from backend.core.knowledge_graph import build_knowledge_graph
    return build_knowledge_graph()


@router.post("/api/knowledge/scan-mac")
async def knowledge_scan_mac(body: MacScanRequest):
    from backend.core.mac_knowledge import scan_and_learn_mac_projects

    result = await scan_and_learn_mac_projects(
        scan_root=body.scan_root,
        learn=body.learn,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Scan Mac fallito"))
    return result


@router.get("/api/chat/history")
async def chat_history(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    sid = session_id or current_session_id()
    data = get_history(sid, limit=limit)
    data["sessions"] = list_sessions(limit=20)
    from backend.core.chat_archive import archive_stats
    data["archive"] = archive_stats()
    return data


@router.get("/api/chat/archive")
async def chat_archive_status():
    from backend.core.chat_archive import archive_stats
    return archive_stats()


@router.post("/api/chat/reprocess")
async def chat_reprocess(
    session_id: str | None = Query(default=None),
    all_pending: bool = Query(default=False),
    force: bool = Query(default=False),
):
    from backend.core.chat_archive import reprocess_pending, reprocess_session

    if all_pending:
        return await reprocess_pending(limit=50)
    sid = session_id or current_session_id()
    return await reprocess_session(sid, force=force)


@router.post("/api/clear")
async def clear():
    new_id = clear_session()
    return {"ok": True, "session_id": new_id}
