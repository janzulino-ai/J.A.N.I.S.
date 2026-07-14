#!/usr/bin/env python3
"""CLI Cursor Agent — output JSON lines per app Windows / bridge WSL."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _run(prompt: str, cwd: str | None) -> int:
    from backend.core.tools.cursor_agent import cursor_code

    async def on_event(ev: dict) -> None:
        print(json.dumps(ev, ensure_ascii=False), flush=True)

    args: dict = {"prompt": prompt}
    if cwd:
        args["cwd"] = cwd
    text = await cursor_code(args, context={"on_event": on_event})
    print(json.dumps({"type": "final", "text": text}, ensure_ascii=False), flush=True)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="JANIS Cursor Agent CLI")
    p.add_argument("--prompt", required=True)
    p.add_argument("--cwd", default=None)
    ns = p.parse_args()
    try:
        raise SystemExit(asyncio.run(_run(ns.prompt, ns.cwd)))
    except Exception as e:
        print(json.dumps({"type": "error", "message": str(e)}), flush=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
