"""Discovery candidati — GitHub, PyPI, watchlist."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from backend.config import settings

logger = logging.getLogger("JANIS.Scout.Discover")

DEFAULT_TOPICS = ["llm", "mcp", "agent", "whisper", "vector-database", "self-hosted"]


def _scout_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "scout" / "candidates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _watchlist_path() -> Path:
    return Path(settings.JANIS_PROJECT_DIR) / "data" / "scout" / "watchlist.yaml"


def load_watchlist() -> list[dict]:
    path = _watchlist_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def list_candidates(*, status: str | None = None) -> list[dict]:
    out = []
    for f in sorted(_scout_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if status and c.get("status") != status:
                continue
            out.append(c)
        except Exception:
            continue
    return out


def save_candidate(candidate: dict) -> dict:
    cid = candidate.get("id") or str(uuid.uuid4())[:12]
    candidate["id"] = cid
    candidate.setdefault("status", "discovered")
    candidate["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _scout_dir() / f"{cid}.json"
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    return candidate


def _github_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "JANIS-Scout/1.0"}
    if settings.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return h


async def discover_github(topic: str, *, limit: int = 5) -> list[dict]:
    q = f"topic:{topic} stars:>100"
    url = "https://api.github.com/search/repositories"
    found: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params={"q": q, "sort": "updated", "per_page": limit}, headers=_github_headers())
            if r.status_code != 200:
                logger.warning("GitHub search %s: %s", topic, r.status_code)
                return []
            for item in r.json().get("items") or []:
                cand = save_candidate({
                    "name": item.get("name"),
                    "source": "github",
                    "url": item.get("html_url"),
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count"),
                    "license": (item.get("license") or {}).get("spdx_id"),
                    "topics": item.get("topics") or [topic],
                    "discovered_via": f"github:{topic}",
                })
                found.append(cand)
    except Exception as e:
        logger.warning("GitHub discover failed: %s", e)
    return found


async def discover_pypi(name: str) -> dict | None:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            info = r.json().get("info") or {}
            return save_candidate({
                "name": info.get("name") or name,
                "source": "pypi",
                "url": info.get("project_url") or info.get("home_page") or f"https://pypi.org/project/{name}/",
                "description": info.get("summary") or "",
                "version": info.get("version"),
                "discovered_via": "pypi",
            })
    except Exception:
        return None


async def discover_watchlist() -> list[dict]:
    found = []
    for item in load_watchlist():
        name = item.get("name") or ""
        url = item.get("url") or ""
        cand = save_candidate({
            "name": name,
            "source": item.get("source", "watchlist"),
            "url": url,
            "topics": item.get("topics") or [],
            "discovered_via": "watchlist",
        })
        found.append(cand)
    return found


async def discover_all(*, topic: str = "", sources: list[str] | None = None) -> dict[str, Any]:
    sources = sources or ["watchlist", "github"]
    all_found: list[dict] = []
    if "watchlist" in sources:
        all_found.extend(await discover_watchlist())
    if "github" in sources:
        topics = [topic] if topic else DEFAULT_TOPICS[:3]
        for t in topics:
            all_found.extend(await discover_github(t, limit=3))
    if "pypi" in sources and topic:
        pkg = re.sub(r"[^a-z0-9_-]", "", topic.lower().replace(" ", "-"))
        if pkg:
            c = await discover_pypi(pkg)
            if c:
                all_found.extend([c])
    return {"ok": True, "count": len(all_found), "candidates": all_found[:20]}
