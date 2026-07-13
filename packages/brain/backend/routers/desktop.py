from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.desktop_state import get_state, set_mode, set_muted, update_idle
from backend.core.open_url import open_system_url

router = APIRouter()


class ModeUpdate(BaseModel):
    mode: str = Field(pattern="^(browser|overlay|screensaver|hidden|wallpaper|fullscreen)$")


class MuteUpdate(BaseModel):
    muted: bool


class IdleUpdate(BaseModel):
    idle_seconds: float = Field(ge=0)


class OpenUrlRequest(BaseModel):
    url: str = Field(min_length=4)


@router.post("/api/desktop/open-url")
async def desktop_open_url(body: OpenUrlRequest):
    """Apre URL nel browser di sistema (Edge/Chrome predefinito)."""
    try:
        url = open_system_url(body.url)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "url": url}


@router.get("/api/desktop/state")
async def desktop_state():
    return get_state()


@router.post("/api/desktop/mode")
async def desktop_mode(body: ModeUpdate):
    return set_mode(body.mode)  # type: ignore[arg-type]


@router.post("/api/desktop/mute")
async def desktop_mute(body: MuteUpdate):
    return set_muted(body.muted)


@router.post("/api/desktop/idle")
async def desktop_idle(body: IdleUpdate):
    return update_idle(body.idle_seconds)
