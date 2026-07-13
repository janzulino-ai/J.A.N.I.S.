import os
import uuid
from typing import Awaitable, Callable

from backend.config import settings
from backend.core.tools.registry import register

EventCallback = Callable[[dict], Awaitable[None]]


@register("cursor_code")
async def cursor_code(args: dict, context: dict | None = None) -> str:
    """
    Delega task di programmazione a Cursor Agent via cursor-sdk.
    Richiede CURSOR_API_KEY in .env
    """
    prompt = (args.get("prompt") or "").strip()
    if not prompt:
        return "Errore: 'prompt' obbligatorio."

    ctx = context or {}
    on_event: EventCallback | None = ctx.get("on_event")
    stream_id = f"cursor-{uuid.uuid4().hex[:8]}"

    async def emit_chunk(chunk: str, done: bool = False) -> None:
        if not on_event:
            return
        await on_event({
            "type": "cursor_stream",
            "id": stream_id,
            "chunk": chunk,
            "done": done,
        })
        await on_event({
            "type": "panel",
            "action": "append",
            "id": "cursor-main",
            "panel_type": "cursor",
            "content": chunk,
        })

    if not settings.CURSOR_API_KEY:
        msg = (
            "Cursor Agent non configurato. Aggiungi CURSOR_API_KEY nel file .env "
            "e attiva PRO nelle impostazioni. "
            f"Task ricevuto: {prompt[:200]}"
        )
        await emit_chunk(msg + "\n", done=True)
        return msg

    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    if not rt.paid_mode:
        msg = (
            "Cursor Agent richiede modalità PRO attiva. "
            "Clicca PRO nella sidebar o usa Ollama per ragionamento locale. "
            f"Task: {prompt[:200]}"
        )
        await emit_chunk(msg + "\n", done=True)
        return msg
    if not rt.cursor_code_enabled:
        msg = "Cursor Agent disabilitato nelle opzioni PRO (codice)."
        await emit_chunk(msg + "\n", done=True)
        return msg

    cwd = args.get("cwd") or settings.JANIS_PROJECT_DIR
    cwd = os.path.abspath(os.path.expanduser(cwd))

    from backend.core.cursor_memory import build_cursor_context, save_cursor_outcome

    memory_ctx = await build_cursor_context(prompt, cwd)
    full_prompt = f"{memory_ctx}\n{prompt}" if memory_ctx else prompt

    if on_event:
        await on_event({
            "type": "panel",
            "action": "open",
            "id": "cursor-main",
            "panel_type": "cursor",
            "title": "Cursor Agent",
            "width": 560,
            "height": 420,
            "manual": True,
        })

    await emit_chunk(f"▶ Cursor Agent avviato\nPrompt: {prompt[:300]}\n\n")

    status = "unknown"
    output = ""
    try:
        import asyncio

        from backend.core.cursor_win_patch import apply_cursor_sdk_patches, reset_cursor_bridge

        apply_cursor_sdk_patches()
        reset_cursor_bridge()
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

        options = AgentOptions(
            api_key=settings.CURSOR_API_KEY,
            model=settings.CURSOR_MODEL,
            local=LocalAgentOptions(cwd=cwd),
        )

        result = await asyncio.to_thread(Agent.prompt, full_prompt, options)
        status = getattr(result, "status", "unknown")
        output = getattr(result, "result", str(result))

        step = 80
        for i in range(0, len(output), step):
            await emit_chunk(output[i : i + step])

        await emit_chunk(f"\n\n[Cursor Agent — {status}]\n", done=True)
        save_cursor_outcome(
            prompt,
            output,
            cwd=cwd,
            status=str(status),
            fix_applied=output[:500] if status in ("completed", "success", "done") else None,
            decision=args.get("memory_decision"),
            gap_resolved=args.get("memory_gap"),
            source=str(args.get("memory_source") or "cursor_code"),
        )
        return f"Cursor Agent [{status}]:\n{output[:10000]}"
    except ImportError:
        msg = (
            "cursor-sdk non installato. Esegui: pip install cursor-sdk\n"
            f"Task in coda: {prompt[:300]}"
        )
        await emit_chunk(msg + "\n", done=True)
        return msg
    except Exception as e:
        msg = f"Errore Cursor Agent: {e}"
        await emit_chunk(msg + "\n", done=True)
        save_cursor_outcome(prompt, msg, cwd=cwd, status="error")
        return msg
