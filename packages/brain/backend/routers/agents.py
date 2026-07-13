"""API agenti — sessioni terminali visibili."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core import agent_host

router = APIRouter()


class SpawnBody(BaseModel):
    command: str = Field(min_length=1)
    topic: str = Field(default="default", max_length=64)
    cwd: str = Field(default="")
    use_wsl: bool = False
    keep_open: bool = True


@router.get("/api/agents/sessions")
async def list_sessions():
    return {"sessions": agent_host.list_sessions()}


@router.get("/api/agents/sessions/{agent_id}")
async def get_session(agent_id: str):
    s = agent_host.get_session(agent_id)
    if not s:
        return {"ok": False, "error": "sessione non trovata"}
    return {"ok": True, "session": s}


@router.post("/api/agents/spawn")
async def spawn_agent(body: SpawnBody):
    s = agent_host.spawn_visible(
        body.command,
        topic=body.topic,
        cwd=body.cwd,
        use_wsl=body.use_wsl,
        keep_open=body.keep_open,
    )
    return {"ok": True, "session": s.to_dict()}


@router.delete("/api/agents/sessions/{agent_id}")
async def kill_session(agent_id: str):
    ok = agent_host.kill_session(agent_id)
    return {"ok": ok}
