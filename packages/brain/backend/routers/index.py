"""API indice cartelle (film, media)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


class FolderScanRequest(BaseModel):
    category: str = Field(default="movies")
    path: str | None = None


@router.get("/api/index/folders")
async def folder_index_status_api():
    from backend.core.folder_index import default_scan_path, get_index_stats
    from backend.core.security import scan_roots

    return {
        "movies": get_index_stats("movies"),
        "defaults": {"movies_path": default_scan_path("movies")},
        "scan_roots": scan_roots(),
    }


@router.post("/api/index/scan")
async def folder_index_scan(body: FolderScanRequest):
    from backend.core.folder_index import run_scan

    try:
        return run_scan(path=body.path, category=body.category or "movies")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/index/search")
async def folder_index_search(
    q: str = Query(..., min_length=1),
    category: str = Query("movies"),
    limit: int = Query(20, ge=1, le=100),
):
    from backend.core.folder_index import get_index_stats, search_index

    stats = get_index_stats(category)
    items = search_index(q, category, limit=limit)
    return {"query": q, "category": category, "stats": stats, "items": items}
