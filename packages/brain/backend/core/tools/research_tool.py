"""Ricerca attendibile + Agent-Reach (W6h)."""
from __future__ import annotations

import json
import logging
from urllib.parse import quote

import httpx

from backend.config import settings
from backend.core.sidecar_call import call_mcp, missing_sidecar, pick_mcp_tool, run_cli
from backend.core.tools.registry import register

logger = logging.getLogger("JANIS.Research")


def _searx_url() -> str:
    return (getattr(settings, "SEARXNG_URL", None) or "http://127.0.0.1:8080").rstrip("/")


async def _searx_search(query: str, *, limit: int = 8) -> list[dict]:
    url = f"{_searx_url()}/search?q={quote(query)}&format=json"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        results = (r.json() or {}).get("results") or []
        out = []
        for item in results[:limit]:
            out.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": (item.get("content") or "")[:400],
                    "engine": item.get("engine"),
                }
            )
        return out


async def _remember_research(query: str, report: str, citations: list[dict]) -> None:
    try:
        from backend.core.tools.memory_tool import remember

        cites = "; ".join(f"{c.get('title')}: {c.get('url')}" for c in citations[:6] if c.get("url"))
        text = f"[research] {query}\n{report[:1500]}\nCitazioni: {cites}"
        await remember({"text": text, "tags": "research,autonomy"})
    except Exception:
        logger.debug("remember research skip", exc_info=True)


@register("research")
async def research(args: dict) -> str:
    """Deep research con citazioni. args: query, save=true"""
    query = (args.get("query") or args.get("q") or args.get("topic") or "").strip()
    if not query:
        return "query obbligatoria"
    save = str(args.get("save", "true")).lower() not in ("0", "false", "no")

    # 1) ii-researcher MCP
    try:
        from backend.core.mcp_client import get_session

        tools = await (await get_session("research")).list_tools()
        name = pick_mcp_tool(tools, "research", "deep_research", "search", "run", "ii_research")
        if name:
            out = await call_mcp("research", name, {"query": query, "q": query, "topic": query})
            if out:
                if save:
                    await _remember_research(query, out, [])
                return out[:12000]
    except Exception:
        pass

    # 2) CLI ii-researcher / gpt-researcher
    for cmd, cli_args in (
        ("ii-researcher", [query]),
        ("gpt-researcher", ["--query", query]),
    ):
        code, out, err = await run_cli(cmd, cli_args, timeout=300)
        if code == 0 and out.strip():
            if save:
                await _remember_research(query, out, [])
            return out[:12000]

    # 3) SearXNG meta-search (sempre utile)
    try:
        hits = await _searx_search(query)
        if hits:
            lines = [f"Research (SearXNG) — {query}", ""]
            for i, h in enumerate(hits, 1):
                lines.append(f"{i}. {h.get('title')}")
                lines.append(f"   {h.get('url')}")
                if h.get("content"):
                    lines.append(f"   {h['content']}")
            report = "\n".join(lines)
            if save:
                await _remember_research(query, report, hits)
            return report
    except Exception as e:
        logger.info("SearXNG fail: %s", e)

    return (
        missing_sidecar("research", "SearXNG su SEARXNG_URL + ii-researcher-mcp")
        + f"\nSEARXNG_URL={_searx_url()}"
    )


@register("reach")
async def reach(args: dict) -> str:
    """Fetch piattaforma (YT/X/Reddit/GH/RSS) via Agent-Reach — solo lettura. args: url|query, source"""
    url = (args.get("url") or "").strip()
    query = (args.get("query") or args.get("q") or "").strip()
    source = (args.get("source") or args.get("platform") or "").strip()
    if not url and not query:
        return "url o query obbligatori"

    # MCP se presente
    out = await call_mcp(
        "agent-reach",
        "fetch",
        {"url": url, "query": query, "source": source},
    )
    if out:
        return out[:12000]

    # CLI Agent-Reach
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
        "https://github.com/Panniantong/Agent-Reach — install CLI, solo read",
    )


@register("research_status")
async def research_status(_args: dict) -> str:
    searx_ok = False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{_searx_url()}/")
            searx_ok = r.status_code < 500
    except Exception:
        pass
    return json.dumps(
        {
            "searxng_url": _searx_url(),
            "searxng_online": searx_ok,
            "tools": ["research", "reach"],
        },
        ensure_ascii=False,
        indent=2,
    )
