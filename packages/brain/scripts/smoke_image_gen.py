"""Smoke image_gen — esegui da WSL: PYTHONPATH=. python scripts/smoke_image_gen.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.tools.media_tool import image_gen, media_status


async def main() -> None:
    print(await media_status({}))
    print("---")
    print(
        await image_gen(
            {
                "prompt": "a blue ceramic cup on wood table, simple photo",
                "width": 512,
                "height": 512,
                "wait": True,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
