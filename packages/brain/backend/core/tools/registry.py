import json
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger("JANIS.Tools")

ToolFn = Callable[..., Awaitable[str]]

_registry: dict[str, ToolFn] = {}


def register(name: str):
    def decorator(fn: ToolFn):
        _registry[name] = fn
        return fn
    return decorator


async def execute_tool(name: str, args: dict, context: dict | None = None) -> str:
    fn = _registry.get(name)
    if not fn:
        from backend.core.capability_gaps import log_gap

        log_gap(
            f"Strumento non disponibile: {name}",
            context=json.dumps(args, ensure_ascii=False)[:500],
            tool=name,
            severity="high",
            proposed_fix=f"Implementare o registrare lo strumento '{name}'",
        )
        return (
            f"Errore: strumento '{name}' non registrato. "
            f"Gap registrato — usa cursor_terminal per proporre una soluzione."
        )
    try:
        import inspect
        sig = inspect.signature(fn)
        if "context" in sig.parameters:
            result = await fn(args or {}, context=context or {})
        else:
            result = await fn(args or {})
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        from backend.core.capability_gaps import log_gap

        log_gap(
            f"Eccezione strumento {name}: {e}",
            context=json.dumps(args, ensure_ascii=False)[:500],
            tool=name,
            severity="high",
        )
        return f"Errore esecuzione '{name}': {e}"


def list_tools() -> list[str]:
    return sorted(_registry.keys())
