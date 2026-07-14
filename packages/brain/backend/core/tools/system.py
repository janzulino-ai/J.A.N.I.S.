import asyncio
from backend.core.tools.registry import register


@register("system_info")
async def system_info(_args: dict) -> str:
    from backend.core.host_awareness import get_awareness_cached, format_awareness_text

    data = await get_awareness_cached(refresh_inventory=True)
    return format_awareness_text(data)


@register("host_capabilities")
async def host_capabilities(_args: dict) -> str:
    """Elenco completo capacità server — hardware, software, tool, canali."""
    from backend.core.host_awareness import get_awareness_cached, format_awareness_text

    refresh = bool((_args or {}).get("refresh"))
    data = await get_awareness_cached(refresh_inventory=refresh)
    return format_awareness_text(data)
