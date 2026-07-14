"""Client Qdrant + embedding Ollama per memoria semantica."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.Qdrant")
COLLECTION = "janis_memory"


async def qdrant_available() -> bool:
    url = (settings.QDRANT_URL or "").rstrip("/")
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{url}/collections")
            return r.status_code == 200
    except Exception:
        return False


async def _embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
            json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text[:8000]},
        )
        r.raise_for_status()
        return r.json().get("embedding") or []


async def ensure_collection() -> bool:
    base = settings.QDRANT_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/collections/{COLLECTION}")
            if r.status_code == 200:
                return True
            r = await client.put(
                f"{base}/collections/{COLLECTION}",
                json={"vectors": {"size": 768, "distance": "Cosine"}},
            )
            return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("Qdrant collection: %s", e)
        return False


async def upsert_memory(text: str, *, metadata: dict | None = None) -> dict[str, Any]:
    if not await qdrant_available():
        return {"ok": False, "error": "Qdrant non raggiungibile"}
    if not await ensure_collection():
        return {"ok": False, "error": "Impossibile creare collection"}
    vec = await _embed(text)
    if not vec:
        return {"ok": False, "error": "Embedding fallito"}
    point_id = str(uuid.uuid4())
    payload = {"text": text[:4000], **(metadata or {})}
    base = settings.QDRANT_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.put(
            f"{base}/collections/{COLLECTION}/points",
            json={"points": [{"id": point_id, "vector": vec, "payload": payload}]},
        )
        r.raise_for_status()
    return {"ok": True, "id": point_id}


async def search_memory(query: str, *, limit: int = 5) -> list[dict]:
    if not await qdrant_available():
        return []
    vec = await _embed(query)
    if not vec:
        return []
    base = settings.QDRANT_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{base}/collections/{COLLECTION}/points/search",
            json={"vector": vec, "limit": limit, "with_payload": True},
        )
        if r.status_code != 200:
            return []
        results = r.json().get("result") or []
    out = []
    for hit in results:
        pl = hit.get("payload") or {}
        out.append({
            "text": pl.get("text", ""),
            "score": hit.get("score"),
            "metadata": {k: v for k, v in pl.items() if k != "text"},
        })
    return out
