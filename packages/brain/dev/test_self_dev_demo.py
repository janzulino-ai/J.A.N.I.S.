import asyncio
from backend.core.brain import process_message, _salvage_tool_call

print("salvage:", _salvage_tool_call('{"tool": "self_develop'))

async def main():
    r = await process_message(
        "bene, hai le capacita per automigliorarti, fammi vedere come fai",
        on_event=None,
        stream_final=False,
    )
    print("---")
    print(r[:800])
    assert "self_develop" not in r.lower() or "fleet" not in r.lower()[:200], "non deve dumpare Fleet"
    assert "preferenz" in r.lower() or "riflett" in r.lower() or "miglior" in r.lower()

asyncio.run(main())
