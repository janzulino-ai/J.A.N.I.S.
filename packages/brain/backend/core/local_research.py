"""Deep research locale: SearXNG + fetch pagine + sintesi Ollama (no API a pagamento)."""
from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import quote

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.LocalResearch")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def searx_base() -> str:
    return (getattr(settings, "SEARXNG_URL", None) or "http://127.0.0.1:8080").rstrip("/")


async def searx_search(query: str, *, limit: int = 8) -> list[dict]:
    url = f"{searx_base()}/search?q={quote(query)}&format=json"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        results = (r.json() or {}).get("results") or []
    out: list[dict] = []
    for item in results[:limit]:
        out.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": (item.get("content") or "")[:500],
                "engine": item.get("engine") or "",
            }
        )
    return out


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


async def fetch_page_text(url: str, *, max_chars: int = 4000) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "JANIS-local-research/1.0"},
        ) as client:
            r = await client.get(url)
            if r.status_code >= 400:
                return ""
            ctype = (r.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
                return ""
            return _strip_html(r.text)[:max_chars]
    except Exception as e:
        logger.debug("fetch %s: %s", url, e)
        return ""


async def ollama_synthesize(query: str, sources: list[dict]) -> str:
    from backend.config import settings as s

    blocks = []
    for i, src in enumerate(sources, 1):
        blocks.append(
            f"[{i}] {src.get('title')}\nURL: {src.get('url')}\n"
            f"Snippet: {src.get('content')}\nEstratto: {src.get('page_text') or '(solo snippet)'}"
        )
    prompt = (
        "Sei un ricercatore. Scrivi in italiano un report breve e attendibile sulla domanda.\n"
        "Usa SOLO le fonti sotto. Cita con [n]. Se le fonti non bastano, dillo.\n"
        "Chiudi con sezione Citazioni (elenco URL).\n\n"
        f"Domanda: {query}\n\nFonti:\n" + "\n\n".join(blocks)
    )
    model = s.OLLAMA_MODEL
    base = s.OLLAMA_BASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Rispondi solo in italiano, con citazioni [n]."},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content") or ""


async def run_local_research(query: str, *, fetch_pages: int = 4, save: bool = True) -> dict:
    """Pipeline completa locale. Ritorna {ok, report, citations, mode}."""
    hits = await searx_search(query)
    if not hits:
        return {"ok": False, "error": "SearXNG senza risultati", "mode": "searxng+ollama"}

    sources = []
    for h in hits[: max(fetch_pages, 1)]:
        page = await fetch_page_text(h["url"]) if h.get("url") else ""
        sources.append({**h, "page_text": page[:3500]})

    report = await ollama_synthesize(query, sources)
    if not report.strip():
        # fallback: solo lista risultati
        lines = [f"Research (SearXNG) — {query}", ""]
        for i, h in enumerate(hits, 1):
            lines.append(f"{i}. {h.get('title')}")
            lines.append(f"   {h.get('url')}")
            if h.get("content"):
                lines.append(f"   {h['content']}")
        report = "\n".join(lines)

    if save:
        try:
            from backend.core.tools.memory_tool import remember

            cites = "; ".join(f"{c.get('title')}: {c.get('url')}" for c in hits[:6])
            await remember(
                {
                    "text": f"[research] {query}\n{report[:1500]}\nCitazioni: {cites}",
                    "tags": "research,autonomy,local",
                }
            )
        except Exception:
            logger.debug("remember skip", exc_info=True)

    return {
        "ok": True,
        "mode": "searxng+ollama",
        "report": report,
        "citations": hits,
    }
