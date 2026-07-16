"""Documenti — Docling (read) + OfficeCLI (edit) via MCP (W6f)."""
from __future__ import annotations

from pathlib import Path

from backend.core.sidecar_call import call_mcp, missing_sidecar, pick_mcp_tool, run_cli
from backend.core.tools.registry import register


async def _list_tools(server: str) -> list[dict]:
    try:
        from backend.core.mcp_client import get_session

        return await (await get_session(server)).list_tools()
    except Exception:
        return []


@register("doc_read")
async def doc_read(args: dict) -> str:
    """Legge PDF/Office con Docling MCP. args: path"""
    path = (args.get("path") or args.get("file") or "").strip()
    if not path:
        return "path obbligatorio"
    p = Path(path)
    if not p.is_file():
        return f"File non trovato: {path}"

    tools = await _list_tools("docling")
    name = pick_mcp_tool(
        tools,
        "convert",
        "convert_document",
        "read_document",
        "parse",
        "docling_convert",
        "extract",
    )
    if name:
        out = await call_mcp("docling", name, {"path": path, "source": path, "file": path})
        if out:
            return out[:12000]

    # fallback: testo grezzo per txt/md
    if p.suffix.lower() in (".txt", ".md", ".csv", ".json", ".log"):
        return p.read_text(encoding="utf-8", errors="replace")[:12000]

    return missing_sidecar("docling", "pip install docling-mcp  (o docling-mcp server)")


@register("office_edit")
async def office_edit(args: dict) -> str:
    """Edita docx/xlsx/pptx via OfficeCLI MCP. args: path, instruction|action, ..."""
    path = (args.get("path") or args.get("file") or "").strip()
    instruction = (args.get("instruction") or args.get("action") or args.get("prompt") or "").strip()
    if not path:
        return "path obbligatorio"
    if not instruction:
        return "instruction obbligatoria (es. 'aggiungi riga tabella...')"

    tools = await _list_tools("officecli")
    name = pick_mcp_tool(tools, "edit", "office_edit", "apply", "run", "execute", "mcp_edit")
    if name:
        out = await call_mcp(
            "officecli",
            name,
            {"path": path, "file": path, "instruction": instruction, "action": instruction},
        )
        if out:
            return out

    code, out, err = await run_cli(
        "officecli",
        ["edit", path, "--instruction", instruction],
        timeout=180,
    )
    if code == 0:
        return out or "officecli ok"
    if code == -1:
        return missing_sidecar("officecli", "install officecli + `officecli mcp`")
    return f"officecli exit {code}: {err or out}"


@register("doc_status")
async def doc_status(_args: dict) -> str:
    import json
    from backend.core.mcp_client import mcp_server_status

    status = await mcp_server_status()
    wanted = {s.get("name"): s for s in status if s.get("name") in ("docling", "officecli")}
    return json.dumps(wanted or {"docling": None, "officecli": None}, ensure_ascii=False, indent=2)
