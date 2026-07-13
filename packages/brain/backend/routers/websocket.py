import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.core.brain import process_message, check_ollama, clear_session, init_session, get_session_history
from backend.core.chat_store import current_session_id
from backend.core.personality import GREETING

router = APIRouter()
logger = logging.getLogger("JANIS.WebSocket")


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}
        self.active: str | None = None

    async def connect(self, client_id: str, ws: WebSocket):
        await ws.accept()
        self.connections[client_id] = ws
        if not self.active:
            self.active = client_id
            await self.send(client_id, {"type": "state", "state": "IDLE"})
        logger.info("Client connesso: %s", client_id)

    def disconnect(self, client_id: str):
        self.connections.pop(client_id, None)
        if self.active == client_id:
            self.active = next(iter(self.connections), None)
        logger.info("Client disconnesso: %s", client_id)

    def set_active(self, client_id: str) -> None:
        cid = client_id.lower().strip()
        if cid in self.connections:
            self.active = cid
            logger.info("Presence active client: %s", cid)

    async def send(self, client_id: str, msg: dict):
        ws = self.connections.get(client_id)
        if ws:
            try:
                await ws.send_json(msg)
            except Exception:
                self.disconnect(client_id)

    def resolve_client(self, sender_id: str) -> str:
        """Instrada eventi verso il device con presenza attiva."""
        from backend.core import presence

        active = presence.active_device_id()
        if presence.should_route_io_to(sender_id):
            return sender_id
        if active in self.connections:
            return active
        return sender_id

    async def send_routed(self, sender_id: str, msg: dict):
        target = self.resolve_client(sender_id)
        await self.send(target, msg)
        if target != sender_id:
            await self.send(sender_id, {"type": "routed", "target": target, **msg})

    async def broadcast(self, msg: dict, exclude: str | None = None):
        for cid in list(self.connections):
            if cid != exclude:
                await self.send(cid, msg)


manager = ConnectionManager()


@router.websocket("/ws/janis")
async def ws_janis(
    websocket: WebSocket,
    device_id: str = Query(default="desktop"),
    session_id: str = Query(default=""),
):
    client_id = device_id.lower().strip()
    await manager.connect(client_id, websocket)

    sid = init_session(session_id.strip() or None)

    if client_id.startswith("pocket"):
        from backend.core import presence
        await presence.claim(client_id, "mobile", session_id=sid)
        manager.set_active(client_id)

    ollama = await check_ollama()
    from backend.core.tools.memory_tool import get_knowledge_stats
    knowledge = get_knowledge_stats()
    await manager.send(client_id, {"type": "system", "ollama": ollama, "knowledge": knowledge, "session_id": sid, "brain_version": 5})
    await manager.send(client_id, {"type": "knowledge_update", **knowledge})
    await manager.send(client_id, {"type": "chat_chunk", "text": GREETING})
    await manager.send(client_id, {"type": "chat_end"})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(client_id, {"type": "error", "message": "JSON non valido"})
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await manager.send(client_id, {"type": "pong"})
                continue

            if msg_type == "clear_session":
                new_sid = clear_session()
                await manager.send(client_id, {"type": "session_cleared", "session_id": new_sid})
                continue

            if msg_type == "autodev_run":
                manager.active = client_id

                async def on_event(event: dict):
                    await manager.send(client_id, event)

                from backend.core.autodev import autocode, autocode_proposal
                from backend.core.reflect import list_proposals

                pid = (msg.get("proposal_id") or "").strip()
                task = (msg.get("task") or "").strip()
                files = msg.get("files") or []
                restart = bool(msg.get("restart"))

                await on_event({"type": "state", "state": "WORKING"})
                await on_event({"type": "autodev", "message": "▶ Ciclo auto-codice avviato"})
                try:
                    if pid:
                        res = await autocode_proposal(pid, restart=restart, emit=on_event)
                    elif task:
                        res = await autocode(task, files=files, restart=restart, emit=on_event)
                    else:
                        code_props = [
                            p for p in list_proposals()
                            if p.get("status") == "open" and p.get("type") == "code"
                        ]
                        code_props.sort(key=lambda p: p.get("priority", "P9"))
                        if not code_props:
                            await on_event({
                                "type": "autodev",
                                "message": "Nessuna proposta di codice aperta. Esegui «reflect» per individuarne, "
                                "oppure passa un task esplicito.",
                                "done": True,
                            })
                            await on_event({"type": "state", "state": "IDLE"})
                            continue
                        chosen = code_props[0]
                        await on_event({"type": "autodev", "message": f"Proposta scelta: {chosen.get('title')}"})
                        res = await autocode_proposal(chosen["id"], restart=restart, emit=on_event)
                    summary = "✓ Auto-codice completato" if res.get("ok") else f"✗ {res.get('error', 'fallito')}"
                    await on_event({"type": "autodev", "message": summary, "done": True, "result": res})
                except Exception as e:
                    logger.exception("autodev_run")
                    await on_event({"type": "autodev", "message": f"Errore: {e}", "done": True})
                await on_event({"type": "state", "state": "IDLE"})
                continue

            if msg_type == "analyze_run":
                manager.active = client_id

                async def on_event(event: dict):
                    await manager.send(client_id, event)

                from backend.core.response_style import compute_tts_text
                from backend.core.tools.registry import execute_tool
                from backend.core.tech_analysis import seed_baseline_research

                seed_baseline_research()
                action = (msg.get("action") or "roadmap").strip().lower()
                topic = (msg.get("topic") or "").strip()
                refs = msg.get("references") or []

                await on_event({"type": "state", "state": "WORKING"})
                await on_event({"type": "analyze", "message": f"▶ Analisi avviata ({action})"})

                try:
                    args: dict = {"action": action}
                    if action == "research":
                        args["topic"] = topic or "OpenClaw e Odysseus vs JANIS — gap e opportunità"
                        args["references"] = refs or ["openclaw", "odysseus", "janis"]
                    result = await execute_tool("analyze", args, context={"on_event": on_event})
                    text = (result or "Analisi completata.").strip()
                    tts = compute_tts_text(text)
                    chunk_size = 80
                    for i in range(0, len(text), chunk_size):
                        await on_event({"type": "chat_chunk", "text": text[i : i + chunk_size]})
                    await on_event({"type": "chat_end", "tts_text": tts})
                    await on_event({"type": "analyze", "message": "✓ Analisi completata", "done": True})
                except Exception as e:
                    logger.exception("analyze_run")
                    await on_event({"type": "analyze", "message": f"Errore: {e}", "done": True})
                await on_event({"type": "state", "state": "IDLE"})
                continue

            if msg_type in ("chat_message", "voice_text", "chat"):
                text = (msg.get("text") or msg.get("message") or "").strip()
                if not text:
                    continue

                manager.active = client_id
                await manager.send_routed(client_id, {"type": "state", "state": "LISTENING"})

                ollama = await check_ollama()
                if not ollama.get("online"):
                    from backend.core.ollama_service import ensure_ollama_running
                    if not await ensure_ollama_running():
                        msg_offline = (
                            "Non posso rispondere: Ollama è offline. "
                            "Avvialo dal menu Start o esegui «ollama serve», poi riprova."
                        )
                        await manager.send(client_id, {"type": "error", "message": "Ollama non raggiungibile"})
                        await manager.send(client_id, {"type": "chat_chunk", "text": msg_offline})
                        await manager.send(client_id, {"type": "chat_end"})
                        await manager.send(client_id, {"type": "state", "state": "IDLE"})
                        continue

                async def on_event(event: dict):
                    await manager.send_routed(client_id, event)

                try:
                    await process_message(text, on_event=on_event, stream_final=True)
                except Exception as e:
                    logger.exception("Errore chat")
                    err = str(e).strip() or "Errore interno"
                    await manager.send_routed(client_id, {"type": "error", "message": err})
                    await manager.send_routed(client_id, {"type": "chat_chunk", "text": f"Errore: {err}"})
                    await manager.send_routed(client_id, {"type": "chat_end"})
                await manager.send_routed(client_id, {"type": "state", "state": "IDLE"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception("WebSocket error")
        manager.disconnect(client_id)
        raise e


@router.websocket("/ws/janice")
async def ws_janice_legacy(
    websocket: WebSocket,
    device_id: str = Query(default="desktop"),
    session_id: str = Query(default=""),
):
    """Alias retrocompatibile."""
    await ws_janis(websocket, device_id=device_id, session_id=session_id)
