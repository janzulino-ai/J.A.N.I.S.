"""Tool autofix — diagnostica e auto-correzione con escalation agente."""
from __future__ import annotations

from backend.core.autofix import run_autofix
from backend.core.tools.registry import register


@register("autofix")
async def autofix_tool(args: dict, context: dict | None = None) -> str:
    """
    Analizza un fallimento e tenta fix locale; se non basta lancia Cursor/terminal.

    args:
      description — cosa è andato storto (obbligatorio se no user_text)
      user_text — messaggio utente originale
      tool_name, tool_result — contesto tool fallito
    """
    ctx = context or {}
    on_event = ctx.get("on_event")
    user_text = (args.get("user_text") or args.get("description") or "").strip()
    if not user_text:
        return "Errore: specifica description o user_text."

    outcome = await run_autofix(
        user_text,
        tool_name=args.get("tool_name"),
        tool_args=args.get("tool_args"),
        tool_result=args.get("tool_result"),
        bad_response=args.get("bad_response"),
        on_event=on_event,
    )
    prefix = "✓ Auto-corretto.\n\n" if outcome.fixed else ""
    if outcome.escalated:
        prefix = f"↗ Escalation a {outcome.agent}.\n\n"
    return prefix + outcome.message
