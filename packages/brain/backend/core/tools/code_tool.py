"""Tool codice — DeusData codebase-memory-mcp (W6b)."""
from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings
from backend.core.sidecar_call import call_mcp, missing_sidecar, pick_mcp_tool, run_cli
from backend.core.tools.registry import register

_SERVER = "codebase-memory"
_HINT = "pip/uv install codebase-memory-mcp oppure vedi DeusData/codebase-memory-mcp"


async def _tools() -> list[dict]:
    try:
        from backend.core.mcp_client import get_session

        sess = await get_session(_SERVER)
        return await sess.list_tools()
    except Exception:
        return []


async def _call_first(candidates: tuple[str, ...], arguments: dict) -> str:
    tools = await _tools()
    name = pick_mcp_tool(tools, *candidates)
    if name:
        out = await call_mcp(_SERVER, name, arguments)
        if out is not None:
            return out
    # CLI fallback
    code, out, err = await run_cli("codebase-memory-mcp", ["--help"], timeout=15)
    if code == -1:
        return missing_sidecar(_SERVER, _HINT)
    return f"MCP tool non trovato tra {candidates}. stderr={err or out[:500]}"


@register("code_search")
async def code_search(args: dict) -> str:
    """Cerca nel grafo codice. args: query, path opz."""
    q = (args.get("query") or args.get("q") or "").strip()
    if not q:
        return "query obbligatoria"
    path = (args.get("path") or args.get("root") or settings.JANIS_WORKSPACE or "").strip()
    return await _call_first(
        ("search", "code_search", "semantic_search", "query", "find"),
        {"query": q, "path": path, "root": path},
    )


@register("code_index")
async def code_index(args: dict) -> str:
    """Indicizza repo/path nel grafo. args: path opz."""
    path = (args.get("path") or args.get("root") or settings.JANIS_WORKSPACE or "").strip()
    if not path:
        path = str(Path(settings.JANIS_PROJECT_DIR))
    return await _call_first(
        ("index", "code_index", "reindex", "build_index", "ingest"),
        {"path": path, "root": path},
    )


@register("code_symbol")
async def code_symbol(args: dict) -> str:
    """Lookup simbolo/definizione. args: name|symbol, path opz."""
    sym = (args.get("name") or args.get("symbol") or args.get("query") or "").strip()
    if not sym:
        return "name/symbol obbligatorio"
    path = (args.get("path") or "").strip()
    return await _call_first(
        ("symbol", "get_symbol", "definition", "goto_definition", "find_symbol"),
        {"name": sym, "symbol": sym, "query": sym, "path": path},
    )


@register("code_context")
async def code_context(args: dict) -> str:
    """Contesto file/simbolo dal grafo. args: path|file|query."""
    target = (args.get("path") or args.get("file") or args.get("query") or "").strip()
    if not target:
        return "path o query obbligatorio"
    return await _call_first(
        ("context", "get_context", "file_context", "explain", "related"),
        {"path": target, "file": target, "query": target},
    )


@register("code_status")
async def code_status(_args: dict) -> str:
    """Stato sidecar codebase-memory."""
    tools = await _tools()
    return json.dumps(
        {
            "server": _SERVER,
            "tools": [t.get("name") for t in tools if isinstance(t, dict)],
            "ready": bool(tools),
            "hint": _HINT if not tools else "ok",
        },
        ensure_ascii=False,
        indent=2,
    )
