"""Verify Mode A sidecar stack (plan A3).

Esegui da WSL con brain attivo:
  cd packages/brain && PYTHONPATH=. python scripts/verify_mode_a.py

Exit:
  0 — doctor non rosso; smoke tool/API completati
  1 — brain non raggiungibile
  2 — doctor rosso (required fail)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BRAIN_URL = os.environ.get("BRAIN_URL", "http://127.0.0.1:8001").rstrip("/")


async def _http_get(path: str) -> dict | None:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{BRAIN_URL}{path}")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"FAIL GET {path}: {e}")
        return None


async def _run_tools() -> dict[str, str]:
    from backend.core.tools.mcp_tool import mcp_status
    from backend.core.tools.media_tool import media_status
    from backend.core.tools.research_tool import research_status, research

    out: dict[str, str] = {}
    out["mcp_status"] = await mcp_status({})
    out["media_status"] = await media_status({})
    out["research_status"] = await research_status({})
    # Query corta — ok se SearXNG offline (report in output)
    out["research"] = await research({"query": "JANIS test", "fetch_pages": 2, "save": "false"})
    return out


async def main() -> int:
    print(f"=== Mode A verify — brain {BRAIN_URL} ===\n")

    status = await _http_get("/api/status")
    if not status or status.get("service") != "JANIS":
        print("Brain non raggiungibile o non JANIS.")
        return 1

    doctor = await _http_get("/api/doctor")
    if not doctor:
        return 1

    summary = doctor.get("summary", "?")
    req_fail = doctor.get("required_fail") or []
    opt_fail = doctor.get("optional_fail") or []
    fabric = doctor.get("fabric") or {}

    print(f"doctor summary={summary}")
    print(f"  required_fail={req_fail}")
    print(f"  optional_fail={len(opt_fail)} items")
    if fabric:
        print(f"  fabric summary={fabric.get('summary')} counts={fabric.get('counts')}")

    caps = await _http_get("/api/capabilities?wave=1")
    if caps:
        print(f"\ncapabilities summary={caps.get('summary')} wave={caps.get('wave')}")
        for c in caps.get("capabilities") or []:
            print(f"  - {c.get('id')}: {c.get('status')} e2e={c.get('e2e')} ({c.get('backend')})")

    print("\n=== tool smoke ===")
    tools_out = await _run_tools()
    for name, body in tools_out.items():
        preview = (body or "")[:240].replace("\n", " ")
        print(f"{name}: {preview}{'…' if len(body or '') > 240 else ''}")

    media = await _http_get("/api/media/images?limit=3")
    if media:
        n = len(media.get("images") or [])
        print(f"\nmedia API: {n} immagini in catalogo")

    print("\n=== done criteria (plan A3) ===")
    print("Target: doctor NON rosso; optional sidecar per verde pieno.")
    print("Smoke: mcp_status, research_status, research (query corta), media_status, /api/capabilities")

    if summary == "rosso" or req_fail:
        print("\nRESULT: FAIL (doctor rosso)")
        return 2

    print(f"\nRESULT: OK (doctor={summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
