"""Cursor parla con JANIS via API — demo interazione bilaterale."""
from __future__ import annotations

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:8010"


async def chat(text: str) -> str:
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(
            f"{BASE}/api/chat",
            json={"text": text},
            headers={"X-JANIS-Client": "cursor"},
        )
        for line in r.text.strip().splitlines():
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if d.get("type") == "final":
                    return d.get("text", "")
        return r.text[:800]


def log_exchange(cursor_msg: str, janis_reply: str, action: str | None = None) -> None:
    from backend.core.cursor_memory import save_cursor_bridge_exchange
    save_cursor_bridge_exchange(cursor_msg, janis_reply, action=action)


async def scan_mac() -> dict:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{BASE}/api/knowledge/scan-mac", json={"learn": False})
        r.raise_for_status()
        return r.json()


async def main() -> None:
    print("=" * 60)
    print("CURSOR  <->  JANIS  (interazione via API)")
    print("=" * 60)

    try:
        st = httpx.get(f"{BASE}/api/status", timeout=5).json()
    except Exception as e:
        print(f"ERRORE: JANIS non raggiungibile su {BASE}: {e}")
        sys.exit(1)

    mem = httpx.get(f"{BASE}/api/memory/brain-status", timeout=5).json()
    print(f"Backend brain_version={st.get('brain_version')} | memoria={mem.get('total')} ({mem.get('mac')} Mac)")
    print()

    dialog = [
        (
            "Cursor",
            "Ciao JANIS, sono Cursor. L'utente agenz vuole vederci interagire. "
            "Conferma che vedi le conoscenze caricate dal scan Mac.",
        ),
        (
            "Cursor",
            "Elenca 4 progetti Mac che conosci con path e una riga su cosa fanno.",
        ),
        (
            "Cursor",
            "Memorizza: Cursor e JANIS collaborano — tu memoria e orchestrazione, io codice e fix. "
            "Usa remember con tag fleet, cursor-bridge.",
        ),
    ]

    for who, msg in dialog:
        print(f"--- {who} ---")
        print(msg)
        print()
        reply = await chat(msg)
        log_exchange(msg, reply)
        print("--- JANIS ---")
        print(reply)
        print()

    print("--- Cursor (azione: scan Mac senza re-learn) ---")
    print("POST /api/knowledge/scan-mac learn=false")
    try:
        scan = await scan_mac()
        n = scan.get("projects_found", scan.get("count", "?"))
        log_exchange("scan Mac projects", f"{n} progetti trovati", action="POST /api/knowledge/scan-mac")
        print("--- JANIS (scan) ---")
        print(f"OK: {scan.get('projects_found', scan.get('count', '?'))} progetti trovati")
        samples = scan.get("projects") or scan.get("items") or []
        for p in (samples[:5] if isinstance(samples, list) else []):
            if isinstance(p, dict):
                print(f"  • {p.get('name', p.get('path', p))}")
            else:
                print(f"  • {p}")
    except Exception as e:
        print(f"Scan: {e}")

    print()
    print("--- Cursor ---")
    print("JANIS, dopo il remember: cosa hai in memoria adesso?")
    print()
    reply = await chat("janis hai parlato con cursor?")
    log_exchange("janis hai parlato con cursor?", reply)
    print("--- JANIS ---")
    print(reply)


if __name__ == "__main__":
    asyncio.run(main())
