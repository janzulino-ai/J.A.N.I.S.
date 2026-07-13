"""Route /server — HUD kiosk solo localhost."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

# routers/ → parents[3] = packages/
_PACKAGES = Path(__file__).resolve().parents[3]
KIOSK_DIR = _PACKAGES / "kiosk"
KIOSK_STATIC = KIOSK_DIR / "static"


def _is_localhost(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


router = APIRouter()


@router.get("/server")
async def server_page(request: Request):
    if not _is_localhost(request):
        return RedirectResponse(url="/", status_code=302)
    page = KIOSK_DIR / "server.html"
    if not page.exists():
        return {"error": "kiosk not found"}
    return FileResponse(page, headers={"Cache-Control": "no-store, must-revalidate"})


def mount_kiosk_static(app) -> None:
    if KIOSK_STATIC.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/kiosk-static", StaticFiles(directory=str(KIOSK_STATIC)), name="kiosk-static")
