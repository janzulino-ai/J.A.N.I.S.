"""Serve file media generati (image_gen) al client Windows/HUD."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config import settings

router = APIRouter(tags=["media"])

_SAFE = re.compile(r"^[A-Za-z0-9._\-]+$")


def media_images_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "images"
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("/api/media/images")
async def list_images(limit: int = 30):
    files = sorted(media_images_dir().glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    files = files[: max(1, min(limit, 100))]
    base = (getattr(settings, "PUBLIC_BASE_URL", None) or f"http://127.0.0.1:{settings.PORT}").rstrip("/")
    return {
        "ok": True,
        "images": [
            {
                "filename": f.name,
                "url": f"{base}/api/media/images/{f.name}",
                "bytes": f.stat().st_size,
            }
            for f in files
        ],
    }


@router.get("/api/media/images/{filename}")
async def get_image(filename: str):
    if not _SAFE.match(filename) or ".." in filename:
        raise HTTPException(400, "filename non valido")
    path = media_images_dir() / filename
    if not path.is_file():
        raise HTTPException(404, "immagine non trovata")
    return FileResponse(path, media_type="image/png", filename=filename)
