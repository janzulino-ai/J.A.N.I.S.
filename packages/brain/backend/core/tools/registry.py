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
    if name in CURSOR_DEPENDENT_TOOLS and not tool_allowed(name):
        return (
            f"Errore: strumento '{name}' disabilitato (local-first). "
            "Usa terminal, read_file, write_file, autofix o add_knowledge_folder."
        )
    fn = _registry.get(name)
    if not fn:
        from backend.core.capability_gaps import log_gap
        from backend.core.runtime_config import load_runtime

        rt = load_runtime()
        hint = (
            "Gap registrato — abilita cursor_code (PRO) per auto-patch, "
            "oppure usa autofix / add_knowledge_folder."
            if rt.cursor_code_enabled
            else "Gap registrato — usa autofix, add_knowledge_folder o terminal (modalità local-first)."
        )

        log_gap(
            f"Strumento non disponibile: {name}",
            context=json.dumps(args, ensure_ascii=False)[:500],
            tool=name,
            severity="high",
            proposed_fix=f"Implementare o registrare lo strumento '{name}'",
        )
        return f"Errore: strumento '{name}' non registrato. {hint}"
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


CURSOR_DEPENDENT_TOOLS = frozenset({
    "cursor_code",
    "cursor_terminal",
    "self_develop",
    "paid_cli_tool",
})


def list_active_tools() -> list[str]:
    """Tool esposti al LLM — esclude Cursor/cloud se disabilitati in runtime."""
    tools = list_tools()
    from backend.core.runtime_config import load_runtime

    rt = load_runtime()
    if not rt.cursor_code_enabled:
        tools = [t for t in tools if t not in CURSOR_DEPENDENT_TOOLS]
    return tools


def tool_allowed(name: str) -> bool:
    return name in list_active_tools()
