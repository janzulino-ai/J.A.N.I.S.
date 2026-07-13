"""One-shot Mac project scan (dev)."""
import asyncio
import json

from backend.core.mac_knowledge import scan_and_learn_mac_projects


async def main() -> None:
    result = await scan_and_learn_mac_projects(learn=True)
    slim = {k: v for k, v in result.items() if k != "nodes"}
    print(json.dumps(slim, ensure_ascii=False, indent=2))
    for p in (result.get("projects") or [])[:10]:
        print(f"  - {p.get('name')}: stacks={p.get('stack_files')}")


if __name__ == "__main__":
    asyncio.run(main())
