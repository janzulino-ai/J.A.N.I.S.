"""Ricerca attendibile locale: SearXNG + Ollama (+ reach opzionale)."""
from __future__ import annotations

import json
import logging

import httpx

from backend.core.local_research import run_local_research, searx_base
from backend.core.sidecar_call import call_mcp, missing_sidecar, run_cli
from backend.core.tools.registry import register

logger = logging.getLogger("JANIS.Research")


@register("research")
async def research(args: dict) -> str:
    """
    Deep research locale (no iscrizione).
    args: query, save=true, fetch_pages=4
    Pipeline: SearXNG → fetch pagine → sintesi Ollama con citazioni.
    """
    query = (args.get("query") or args.get("q") or args.get("topic") or "").strip()
    if not query:
        return "query obbligatoria"
    save = str(args.get("save", "true")).lower() not in ("0", "false", "no")
    fetch_pages = int(args.get("fetch_pages") or 4)

    try:
        result = await run_local_research(query, fetch_pages=fetch_pages, save=save)
        if result.get("ok") and result.get("report"):
            header = f"[mode={result.get('mode')}]\n"
            return (header + result["report"])[:12000]
        err = result.get("error") or "research fallita"
        logger.info("local research: %s", err)
    except Exception as e:
        logger.info("local research exception: %s", e)
        err = str(e)

    return (
        missing_sidecar(
            "research-local",
            "Avvia SearXNG (docker compose infra/sidecars/docker-compose.searxng.yml) "
            "e Ollama; poi configure-sidecar-urls.sh",
        )
        + f"\nSEARXNG_URL={searx_base()}\ndettaglio: {err}"
    )


@register("reach")
async def reach(args: dict) -> str:
    """Fetch piattaforma (YT/X/Reddit/GH/RSS) via Agent-Reach — solo lettura. args: url|query, source"""
    url = (args.get("url") or "").strip()
    query = (args.get("query") or args.get("q") or "").strip()
    source = (args.get("source") or args.get("platform") or "").strip()
    if not url and not query:
        return "url o query obbligatori"

    out = await call_mcp(
        "agent-reach",
        "fetch",
        {"url": url, "query": query, "source": source},
    )
    if out:
        return out[:12000]

    cli_args: list[str] = []
    if url:
        cli_args = ["fetch", url]
    elif source:
        cli_args = ["search", source, query]
    else:
        cli_args = ["search", query]

    for cmd in ("agent-reach", "reach"):
        code, stdout, err = await run_cli(cmd, cli_args, timeout=180)
        if code == 0 and stdout.strip():
            return stdout[:12000]
        if code == -1:
            continue
        if stdout or err:
            return (stdout or err)[:8000]

    return missing_sidecar(
        "agent-reach",
        "https://github.com/Panniantong/Agent-Reach — install CLI, solo read (opzionale)",
    )


@register("research_status")
async def research_status(_args: dict) -> str:
    searx_ok = False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{searx_base()}/")
            searx_ok = r.status_code < 500
    except Exception:
        pass
    ollama_ok = False
    try:
        from backend.config import settings

        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            ollama_ok = r.status_code < 500
    except Exception:
        pass
    return json.dumps(
        {
            "pipeline": "searxng+ollama (locale, no signup)",
            "searxng_url": searx_base(),
            "searxng_online": searx_ok,
            "ollama_online": ollama_ok,
            "note": "ii-researcher upstream richiede Tavily/SerpAPI — non usato di default",
            "tools": ["research", "reach"],
        },
        ensure_ascii=False,
        indent=2,
    )
