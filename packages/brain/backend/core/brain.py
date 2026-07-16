import json
import logging
import re
import uuid
from collections import deque
from typing import Callable, Awaitable

from backend.config import settings
from backend.core.llm_router import chat as llm_chat, chat_stream as llm_chat_stream
from backend.core.tools.registry import execute_tool, list_tools, list_active_tools, tool_allowed

logger = logging.getLogger("JANIS.Brain")

EventCallback = Callable[[dict], Awaitable[None]]


_EMPTY_REPLY_FALLBACK = (
    "Mi scuso, il modello locale non ha prodotto una risposta. "
    "Riprova tra un attimo o riformula la domanda."
)


def _fallback_from_tool(tool_name: str | None, tool_result: str | None) -> str | None:
    """Se Ollama risponde vuoto dopo un tool, usa l'esito del tool."""
    if not tool_result or not tool_result.strip():
        return None
    if tool_result.startswith("Errore"):
        return tool_result[:2000]
    body = tool_result.strip()
    if len(body) > 2800:
        body = body[:2800] + "…"
    if tool_name:
        return f"Ecco l'esito ({tool_name}):\n\n{body}"
    return body


async def _deliver_final(
    final: str,
    emit: EventCallback,
    stream_final: bool,
) -> str:
    """Invia risposta all'UI garantendo testo non vuoto."""
    from backend.core.response_style import compute_tts_text

    text = (final or "").strip() or _EMPTY_REPLY_FALLBACK
    tts_text = compute_tts_text(text)
    _session_history.append({"role": "assistant", "content": text})
    _persist_message("assistant", text)
    await emit({"type": "state", "state": "SPEAKING"})
    if stream_final:
        chunk_size = 80
        for i in range(0, len(text), chunk_size):
            await emit({"type": "chat_chunk", "text": text[i : i + chunk_size]})
        await emit({"type": "chat_end", "tts_text": tts_text})
    from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
    increment_janis_interaction()
    await emit({"type": "knowledge_grow", "amount": 2})
    await emit({"type": "knowledge_update", **get_knowledge_stats()})
    _log_chat_out(text)
    return text


def _log_chat_out(text: str) -> None:
    logger.info("CHAT OUT <<< %s", (text or "")[:500])


_session_history: deque[dict] = deque(maxlen=40)


def _persist_message(role: str, content: str) -> None:
    from backend.core.chat_store import append_message
    append_message(role, content)


def _restore_session_from_disk(session_id: str | None = None) -> None:
    from backend.core.chat_store import load_messages, set_session
    if session_id:
        set_session(session_id)
    msgs = load_messages(session_id, limit=40)
    _session_history.clear()
    for msg in msgs:
        _session_history.append(msg)

_WIN_PATH_RE = re.compile(
    r'(?<![A-Za-z0-9])([A-Za-z]:\\(?:[^<>"|\n\r]+?))(?=[\s\.,;:!?\)]|$|")',
    re.IGNORECASE,
)
_FOLDER_LEARN_KEYWORDS = (
    "impara", "conosci", "indicizza", "scansiona", "aggiungi", "cartella",
    "video", "film", "brain", "neuroni", "memoria", "vault", "conoscenza",
)


async def _auto_learn_folder_if_requested(user_text: str, emit: EventCallback) -> str | None:
    """Esegue add_knowledge_folder quando l'utente indica un path Windows esplicito."""
    lower = user_text.lower()
    if not any(k in lower for k in _FOLDER_LEARN_KEYWORDS):
        return None

    paths = [p.rstrip("\\/.,") for p in _WIN_PATH_RE.findall(user_text)]
    if not paths:
        return None

    from backend.core.security import validate_local_folder

    path = paths[0]
    try:
        validate_local_folder(path)
    except FileNotFoundError:
        return (
            f"Non trovo la cartella `{path}`. Verifica che il disco sia collegato "
            f"e che il percorso sia corretto."
        )
    except PermissionError as e:
        return str(e)

    await emit({"type": "state", "state": "ACTING"})
    await emit({
        "type": "tool_start",
        "tool": "add_knowledge_folder",
        "args": {"path": path},
        "reason": "Apprendimento cartella richiesto dall'utente",
    })
    result = await execute_tool("add_knowledge_folder", {"path": path, "learn": True})
    await emit({"type": "tool_end", "tool": "add_knowledge_folder", "result": result[:2000]})

    from backend.core.knowledge_graph import node_from_memory
    from backend.core.tools.memory_tool import _load, get_knowledge_stats

    mems = _load()
    for entry in [e for e in mems if "knowledge-folder" in (e.get("tags") or [])][-6:]:
        await emit({"type": "brain_node", "node": node_from_memory(entry)})
    await emit({"type": "knowledge_update", **get_knowledge_stats()})
    await emit({"type": "knowledge_grow", "amount": 3})

    final = result if result.strip() else f"Cartella `{path}` registrata."
    _session_history.append({"role": "assistant", "content": final})
    _persist_message("assistant", final)
    await emit({"type": "state", "state": "SPEAKING"})
    await emit({"type": "chat_chunk", "text": final})
    await emit({"type": "chat_end"})
    _log_chat_out(final)
    return final


async def _fix_false_memory_denial(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
    bad_response: str,
) -> str | None:
    """Se l'LLM nega la memoria ma long_term ha dati, risponde con memory_status."""
    from backend.core.tools.memory_tool import (
        _load,
        looks_like_false_memory_denial,
        memory_status,
    )

    if not looks_like_false_memory_denial(bad_response):
        return None
    if not _load():
        return None

    await emit({"type": "state", "state": "ACTING"})
    await emit({
        "type": "tool_start",
        "tool": "memory_status",
        "args": {},
        "reason": "Correzione: memoria negata dall'LLM ma dati presenti",
    })
    status = await memory_status({})
    await emit({"type": "tool_end", "tool": "memory_status", "result": status[:2000]})

    final = (
        "Sì, ho accesso alla memoria persistente. Ecco cosa contiene:\n\n"
        f"{status}"
    )
    _session_history.append({"role": "assistant", "content": final})
    _persist_message("assistant", final)
    await emit({"type": "state", "state": "SPEAKING"})
    if stream_final:
        chunk_size = 80
        for i in range(0, len(final), chunk_size):
            await emit({"type": "chat_chunk", "text": final[i : i + chunk_size]})
        await emit({"type": "chat_end"})
    from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
    increment_janis_interaction()
    await emit({"type": "knowledge_grow", "amount": 2})
    await emit({"type": "knowledge_update", **get_knowledge_stats()})
    _log_chat_out(final)
    return final


async def _handle_memory_write_intent(
    user_text: str,
    emit: EventCallback | None = None,
    stream_final: bool = False,
) -> str | None:
    """Salva regole o guida l'utente — non elencare statistiche memoria."""
    from backend.core.tools.memory_tool import (
        build_memory_write_response,
        is_memory_write_intent,
        parse_inline_remember,
    )
    from backend.core.tools.registry import execute_tool

    if not is_memory_write_intent(user_text):
        return None

    async def _emit(event: dict) -> None:
        if emit:
            await emit(event)

    inline = parse_inline_remember(user_text)
    if inline:
        await _emit({"type": "state", "state": "ACTING"})
        await _emit({"type": "tool_start", "tool": "remember", "args": {"text": inline[:80]}})
        result = await execute_tool(
            "remember",
            {"text": inline, "tags": ["regola", "user"], "source": "user"},
        )
        await _emit({"type": "tool_end", "tool": "remember", "result": result[:500]})
        final = f"Salvato.\n\n{result}\n\nLa userò nelle prossime chat."
    else:
        final = build_memory_write_response(user_text)

    _session_history.append({"role": "assistant", "content": final})
    _persist_message("assistant", final)
    await _emit({"type": "state", "state": "SPEAKING"})
    if stream_final:
        chunk_size = 80
        for i in range(0, len(final), chunk_size):
            await _emit({"type": "chat_chunk", "text": final[i : i + chunk_size]})
        await _emit({"type": "chat_end"})
    from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
    increment_janis_interaction()
    await _emit({"type": "knowledge_grow", "amount": 2})
    await _emit({"type": "knowledge_update", **get_knowledge_stats()})
    _log_chat_out(final)
    return final


async def _answer_memory_query_directly(
    user_text: str,
    emit: EventCallback | None = None,
    stream_final: bool = False,
) -> str | None:
    """Risposta deterministica per domande sulla memoria — non affida all'LLM locale."""
    from backend.core.tools.memory_tool import build_memory_read_response, is_memory_query

    if not is_memory_query(user_text):
        return None

    async def _emit(event: dict) -> None:
        if emit:
            await emit(event)

    await _emit({"type": "state", "state": "ACTING"})
    final = build_memory_read_response(user_text)
    await _emit({"type": "tool_end", "tool": "memory_read", "result": final[:2000]})

    _session_history.append({"role": "assistant", "content": final})
    _persist_message("assistant", final)
    await _emit({"type": "state", "state": "SPEAKING"})
    if stream_final:
        chunk_size = 80
        for i in range(0, len(final), chunk_size):
            await _emit({"type": "chat_chunk", "text": final[i : i + chunk_size]})
        await _emit({"type": "chat_end"})
    from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
    increment_janis_interaction()
    await _emit({"type": "knowledge_grow", "amount": 2})
    await _emit({"type": "knowledge_update", **get_knowledge_stats()})
    _log_chat_out(final)
    return final


async def _apply_autofix_if_needed(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
    *,
    tool_name: str | None = None,
    tool_args: dict | None = None,
    tool_result: str | None = None,
    bad_response: str | None = None,
) -> str | None:
    """Ritorna messaggio se autofix ha corretto o escalato; altrimenti None."""
    if bad_response:
        memory_fix = await _fix_false_memory_denial(
            user_text, emit, stream_final, bad_response,
        )
        if memory_fix:
            return memory_fix

    from backend.core.autofix import looks_like_false_access_block, run_autofix

    trigger = bool(bad_response and looks_like_false_access_block(bad_response, user_text))
    if tool_result:
        trigger = trigger or tool_result.startswith("Errore") or "fallito" in tool_result.lower()
    if not trigger:
        return None

    outcome = await run_autofix(
        user_text,
        tool_name=tool_name,
        tool_args=tool_args,
        tool_result=tool_result,
        bad_response=bad_response,
        on_event=emit,
    )
    if not (outcome.fixed or outcome.escalated):
        return None

    final = outcome.message
    _session_history.append({"role": "assistant", "content": final})
    _persist_message("assistant", final)
    await emit({"type": "state", "state": "SPEAKING"})
    if stream_final:
        chunk_size = 80
        for i in range(0, len(final), chunk_size):
            await emit({"type": "chat_chunk", "text": final[i : i + chunk_size]})
        await emit({"type": "chat_end"})
    from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
    increment_janis_interaction()
    await emit({"type": "knowledge_grow", "amount": 2 if outcome.fixed else 1})
    await emit({"type": "knowledge_update", **get_knowledge_stats()})
    _log_chat_out(final)
    return final


def get_session_history(session_id: str | None = None) -> list[dict]:
    if session_id:
        from backend.core.chat_store import get_history
        items = get_history(session_id, limit=40).get("messages") or []
        return [{"role": m["role"], "content": m["content"]} for m in items if m.get("role")]
    return list(_session_history)


def clear_session() -> str:
    from backend.core.chat_store import current_session_id, new_session
    import asyncio
    import logging

    log = logging.getLogger("JANIS.Brain")
    old_sid = current_session_id()
    if old_sid:
        try:
            from backend.core.chat_archive import reprocess_session

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(reprocess_session(old_sid))
            else:
                loop.run_until_complete(reprocess_session(old_sid))
        except Exception as e:
            log.warning("chat archive on clear_session failed: %s", e)
    _session_history.clear()
    return new_session()


def init_session(session_id: str | None = None) -> str:
    """Ripristina o avvia sessione chat (RAM + disco)."""
    from backend.core.chat_store import current_session_id, new_session, set_session
    if session_id:
        set_session(session_id)
        _restore_session_from_disk(session_id)
        return session_id
    if not _session_history:
        _restore_session_from_disk()
    return current_session_id()


def _extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return _salvage_tool_call(text)


def _salvage_tool_call(text: str) -> dict | None:
    """Recupera tool/args da JSON troncato o malformato (es. gemma4)."""
    if not text or '"tool"' not in text:
        return None
    m = re.search(r'"tool"\s*:\s*"([a-zA-Z0-9_]+)', text)
    if not m:
        return None
    tool = m.group(1)
    args: dict = {}
    args_m = re.search(r'"args"\s*:\s*(\{.*)', text, re.DOTALL)
    if args_m:
        fragment = args_m.group(1)
        for end in range(len(fragment), 0, -1):
            try:
                args = json.loads(fragment[:end])
                break
            except json.JSONDecodeError:
                continue
    if tool == "self_develop" and not args:
        args = {"action": "status"}
    return {"tool": tool, "args": args}


def _looks_like_raw_tool_json(text: str) -> bool:
    t = (text or "").lstrip()
    return t.startswith("{") and '"tool"' in t[:120]


async def _auto_improve_if_requested(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
) -> str | None:
    """Auto-miglioramento generico → reflect (impara preferenze), non dump Fleet."""
    from backend.core.reflect import list_proposals
    from backend.core.response_style import conversational_improve_summary

    lower = user_text.lower()
    improve_triggers = (
        "automiglior", "auto-miglior", "migliorarti", "auto miglior",
        "fammi vedere come", "mostrami come", "dimostra come",
        "imparare le mie", "impara dalle", "impara le mie", "auto-valut", "auto valut",
        "rifletti su te", "rifletti e", "valutati",
    )
    fleet_only = (
        "fleet", "flotta", "fase 1", "fase 2", "fase 3", "fase 4", "fase 5",
        "implement_phase", "bridge mac", "progetto fleet", "nodi mac", "mac bridge",
    )
    skip_for_specific_fix = (
        "whatsapp", "microfono", "mic ", "tts", "voce", "gruppo whats",
    )

    if not any(k in lower for k in improve_triggers):
        return None
    if any(k in lower for k in fleet_only) and not any(k in lower for k in ("preferenz", "rifletti", "impara")):
        return None
    if any(k in lower for k in skip_for_specific_fix):
        return None

    await emit({"type": "state", "state": "ACTING"})
    await emit({
        "type": "tool_start",
        "tool": "reflect",
        "args": {"action": "run"},
        "reason": "Auto-miglioramento: riflessione e apprendimento preferenze",
    })
    result = await execute_tool("reflect", {"action": "run"}, context={"on_event": emit})
    await emit({"type": "tool_end", "tool": "reflect", "result": (result or "")[:2000]})

    open_code = [
        p for p in list_proposals()
        if p.get("status") == "open" and p.get("type") == "code"
    ]
    open_code.sort(key=lambda p: p.get("priority", "P9"))
    code_title = open_code[0]["title"] if open_code else None

    summary_line = ""
    if result and "Sintesi:" in result:
        summary_line = result.split("Sintesi:", 1)[1].split("\n", 1)[0].strip()

    prefs_n = result.count("•") if result and "Preferenze" in result else 0
    final = conversational_improve_summary(summary_line, prefs_n, code_title)
    return await _deliver_final(final, emit, stream_final)


async def _answer_whatsapp_if_asked(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
) -> str | None:
    """Risposta onesta su WhatsApp — verifica bridge reale."""
    lower = user_text.lower()
    if "whatsapp" not in lower:
        return None
    if not any(k in lower for k in (
        "gruppo", "group", "aggiung", "integr", "chat", "messagg", "numero",
        "invia", "mandare", "colleg", "configur", "funziona", "test",
    )):
        return None

    from backend.config import settings
    bridge_ok = bool((settings.WHATSAPP_BRIDGE_URL or "").strip())

    group = any(k in lower for k in ("gruppo", "group"))
    if bridge_ok:
        spoken = (
            "WhatsApp è collegato via bridge Node. "
            "Posso inviare con lo strumento whatsapp_send se mi dai destinatario e testo."
        )
        if group:
            spoken += " Per i gruppi serve l'id gruppo e di solito una menzione."
    elif group:
        spoken = (
            "WhatsApp bridge non attivo. Per i gruppi servono bridge Node (whatsapp-web.js), "
            "WHATSAPP_BRIDGE_URL in .env e regole menzione."
        )
    else:
        spoken = (
            "WhatsApp: tool whatsapp_send presente ma bridge non configurato. "
            "Imposta WHATSAPP_BRIDGE_URL e avvia packages/brain/bridge/whatsapp/bridge.mjs"
        )

    detail = (
        f"\n\n---\nBridge: {'OK ' + settings.WHATSAPP_BRIDGE_URL if bridge_ok else 'non configurato'}. "
        "Vedi docs/CHANNELS.md."
    )
    return await _deliver_final(spoken + detail, emit, stream_final)


async def _auto_analyze_if_requested(
    user_text: str,
    emit: EventCallback,
    stream_final: bool,
) -> str | None:
    """Analisi/roadmap feature — stesso lavoro dell'assistente dev."""
    lower = user_text.lower()
    triggers = (
        "analizz", "confronta", "openclaw", "odysseus", "odyssey",
        "roadmap", "cosa possiamo implement", "cosa implementare",
        "gap ", "reverse eng", "pianific", "studio open", "lista delle cose",
    )
    if not any(k in lower for k in triggers):
        return None

    await emit({"type": "state", "state": "ACTING"})

    refs: list[str] = []
    if "openclaw" in lower:
        refs.append("openclaw")
    if "odysseus" in lower or "odyssey" in lower or "pewdiepie" in lower:
        refs.append("odysseus")
    if "janis" in lower or not refs:
        refs.append("janis")

    if any(k in lower for k in ("roadmap", "cosa possiamo", "cosa implement", "lista delle cose", "lista possib")):
        await emit({"type": "tool_start", "tool": "analyze", "args": {"action": "roadmap"}, "reason": "Roadmap feature"})
        result = await execute_tool("analyze", {"action": "roadmap"}, context={"on_event": emit})
        await emit({"type": "tool_end", "tool": "analyze", "result": (result or "")[:2000]})
        intro = "Ecco la roadmap prioritizzata — analisi, fleet e proposte aperte."
        final = f"{intro}\n\n{result}"
        return await _deliver_final(final, emit, stream_final)

    topic = user_text.strip()
    if len(topic) > 300:
        topic = topic[:300]
    await emit({
        "type": "tool_start",
        "tool": "analyze",
        "args": {"action": "research", "topic": topic},
        "reason": "Analisi tecnologica vs JANIS",
    })
    result = await execute_tool(
        "analyze",
        {"action": "research", "topic": topic, "references": refs},
        context={"on_event": emit},
    )
    await emit({"type": "tool_end", "tool": "analyze", "result": (result or "")[:2000]})
    final = result or "Analisi completata."
    return await _deliver_final(final, emit, stream_final)


async def _emit_tool_side_effects(
    tool_name: str,
    tool_args: dict,
    result: str,
    emit: EventCallback,
) -> None:
    try:
        data = json.loads(result)
        if data.get("_panel_event"):
            clean = {k: v for k, v in data.items() if k != "_panel_event"}
            if "type" in clean and "panel_type" not in clean:
                clean["panel_type"] = clean.pop("type")
            await emit({"type": "panel", **clean})
            return
    except (json.JSONDecodeError, TypeError):
        pass

    if tool_name == "terminal":
        cmd = tool_args.get("command", "")
        await emit({
            "type": "panel",
            "action": "append",
            "id": "terminal-main",
            "panel_type": "terminal",
            "content": f"$ {cmd}\n{result}\n",
        })
    elif tool_name == "mac_ssh":
        pass  # streaming già emesso da mac_ssh via on_event


AGENT_TOOLS = frozenset({
    "terminal", "cursor_code", "cursor_terminal", "panel", "open_browser", "read_file", "write_file",
    "self_develop", "mac_ssh", "autofix",
})


def _agent_label(tool_name: str, tool_args: dict) -> str:
    if tool_name == "panel":
        return f"panel:{tool_args.get('type') or tool_args.get('action') or 'ui'}"
    if tool_name == "cursor_code":
        return "cursor-agent"
    if tool_name == "mac_ssh":
        return "mac-mini"
    return tool_name


async def _emit_brain_agent(tool_name: str, tool_args: dict, reason: str, emit: EventCallback) -> str:
    agent_id = f"agent-{tool_name}-{uuid.uuid4().hex[:8]}"
    if tool_name in AGENT_TOOLS or tool_name.startswith("cursor"):
        await emit({
            "type": "brain_agent",
            "action": "spawn",
            "id": agent_id,
            "label": _agent_label(tool_name, tool_args),
            "tool": tool_name,
            "reason": (reason or "")[:120],
        })
    return agent_id


async def _emit_brain_agent_end(agent_id: str | None, emit: EventCallback) -> None:
    if agent_id:
        await emit({"type": "brain_agent", "action": "dismiss", "id": agent_id})


def _base_system_prompt() -> str:
    """Prompt compatto su Linux server — gemma4 CPU non regge il prompt Windows completo."""
    import platform
    if platform.system() == "Linux":
        return (
            "Sei JANIS — brain sul server Linux (Just Another Neuralgic Improving Server).\n"
            "Rispondi SEMPRE in italiano, breve e utile.\n"
            "Protocollo: JSON {\"tool\":\"nome\",\"args\":{...},\"reason\":\"...\"} oppure {\"final\":\"risposta\"}.\n"
            "Per hardware/software/periferiche usa host_capabilities o system_info — non inventare.\n"
            "Tool chiave: terminal, read_file, write_file, remember, recall, "
            "code_search, research, reach, doc_read, image_gen, describe_vision, "
            "fleet_execute, mobile_ui, board_status, janis_doctor, mcp_status.\n"
            "Windows è solo VM win-vm su questo host. Mac via SSH se online.\n"
        )
    return settings.JANIS_SYSTEM_PROMPT


async def process_message(
    user_text: str,
    on_event: EventCallback | None = None,
    stream_final: bool = False,
) -> str:
    async def emit(event: dict):
        if on_event:
            await on_event(event)

    _session_history.append({"role": "user", "content": user_text})
    _persist_message("user", user_text)
    logger.info("CHAT IN  >>> %s", user_text[:500])

    from backend.core.tools.memory_tool import increment_user_message
    increment_user_message()

    from backend.core.host_awareness import is_awareness_query
    from backend.core.intent_router import (
        board_goal_context,
        classify_intent,
        intent_system_block,
        maybe_fast_path,
    )

    tools_list = ", ".join(list_active_tools())
    system = _base_system_prompt() + f"\n\nStrumenti attivi: {tools_list}"
    hint = classify_intent(user_text)
    system += intent_system_block(hint)
    system += board_goal_context()

    fast = await maybe_fast_path(user_text)
    if fast:
        return await _deliver_final(fast, emit, stream_final)

    # Snapshot compatto (non l'inventario completo — gemma4 su CPU impiega minuti)
    if is_awareness_query(user_text):
        from backend.core.host_awareness import get_awareness_context_for_brain
        awareness_ctx = await get_awareness_context_for_brain()
        if awareness_ctx:
            system += "\n\n" + awareness_ctx
    else:
        try:
            from backend.core.host_awareness import get_awareness_cached
            snap = await get_awareness_cached()
            cpu = (snap.get("cpu") or {}).get("model", "?")
            system += (
                f"\n\nHOST: {snap.get('hostname')} · {cpu} · {snap.get('memory_gb')}GB RAM · "
                f"LLM {((snap.get('llm') or {}).get('active'))} · "
                f"{snap.get('tool_count', 0)} tool. Per inventario completo usa tool host_capabilities."
            )
        except Exception:
            pass

    from backend.core.self_dev import SELF_DEV_KEYWORDS, get_context_for_brain as self_dev_context

    lower = user_text.lower()
    if any(k in lower for k in SELF_DEV_KEYWORDS):
        system += "\n\n" + self_dev_context()

    from backend.core.folder_knowledge import get_context_for_brain as folder_knowledge_context
    folder_ctx = folder_knowledge_context(user_text)
    if folder_ctx:
        system += "\n\n" + folder_ctx

    from backend.core.mac_knowledge import get_context_for_brain as mac_knowledge_context
    mac_ctx = mac_knowledge_context(user_text)
    if mac_ctx:
        system += "\n\n" + mac_ctx

    from backend.core.tools.memory_tool import get_memory_context_for_brain
    mem_ctx = get_memory_context_for_brain(user_text)
    if mem_ctx:
        system += "\n\n" + mem_ctx

    from backend.core.reflect import get_learned_preferences_context
    pref_ctx = get_learned_preferences_context()
    if pref_ctx:
        system += "\n\n" + pref_ctx

    from backend.core.tech_analysis import get_roadmap_context, seed_baseline_research

    seed_baseline_research()
    _plan_kw = (
        "analizz", "confronta", "openclaw", "odysseus", "roadmap", "implement",
        "feature", "gap", "pianific", "cosa possiamo", "cosa implement",
    )
    if any(k in lower for k in _plan_kw):
        rm_ctx = get_roadmap_context()
        if rm_ctx:
            system += "\n\n" + rm_ctx

    from backend.core.cursor_memory import get_cursor_bridge_context
    from backend.core.tools.memory_tool import is_memory_query

    cursor_ctx = get_cursor_bridge_context()
    if cursor_ctx and ("cursor" in lower or is_memory_query(user_text)):
        system += "\n\n" + cursor_ctx

    if mac_ctx or mem_ctx or cursor_ctx:
        system += (
            "\n\nNOTA MEMORIA: I blocchi PROGETTI MAC / MEMORIA ATTIVA / SESSIONI CURSOR sopra "
            "contengono conoscenza già caricata. Se l'utente chiede cosa ricordi, se hai "
            "parlato con Cursor, o cosa c'è in memoria, rispondi usando QUEI dati — "
            "non dire che la memoria è vuota."
        )

    system += (
        "\n\nACCESSO FILE SYSTEM (Windows):\n"
        "Operi sul PC locale dell'utente con accesso a TUTTI i dischi montati "
        "(C:, D:, H:, USB, …). NON esiste un sandbox che blocca H: o altre unità.\n"
        "Se l'utente indica un percorso tipo H:\\Video, usa add_knowledge_folder — "
        "non dire mai di copiare i file altrove senza aver provato lo strumento."
    )

    auto_learn = await _auto_learn_folder_if_requested(user_text, emit)
    if auto_learn:
        from backend.core.tools.memory_tool import get_knowledge_stats, increment_janis_interaction
        increment_janis_interaction()
        return auto_learn

    from backend.core.autonomy import process_autonomy

    autonomy_answer = await process_autonomy(user_text, emit, stream_final, _deliver_final)
    if autonomy_answer:
        return autonomy_answer

    memory_write = await _handle_memory_write_intent(user_text, emit, stream_final)
    if memory_write:
        return memory_write

    memory_answer = await _answer_memory_query_directly(user_text, emit, stream_final)
    if memory_answer:
        return memory_answer

    if is_awareness_query(user_text):
        await emit({"type": "state", "state": "ACTING"})
        from backend.core.host_awareness import answer_awareness_query
        final = await answer_awareness_query(user_text)
        return await _deliver_final(final, emit, stream_final)

    whatsapp_answer = await _answer_whatsapp_if_asked(user_text, emit, stream_final)
    if whatsapp_answer:
        return whatsapp_answer

    analyze_answer = await _auto_analyze_if_requested(user_text, emit, stream_final)
    if analyze_answer:
        return analyze_answer

    improve_answer = await _auto_improve_if_requested(user_text, emit, stream_final)
    if improve_answer:
        return improve_answer

    messages = [{"role": "system", "content": system}]
    for msg in _session_history:
        messages.append(msg)

    await emit({"type": "state", "state": "THINKING"})

    max_iter = (
        settings.SELF_DEV_MAX_ITERATIONS
        if any(k in lower for k in SELF_DEV_KEYWORDS)
        else settings.MAX_TOOL_ITERATIONS
    )

    last_tool_name: str | None = None
    last_tool_result: str | None = None

    for iteration in range(max_iter):
        raw, provider = await llm_chat(
            messages,
            user_text=user_text,
            tool_loop=iteration > 0,
            iteration=iteration,
        )
        logger.info("Brain iter %d (%s): %s", iteration, provider, (raw or "")[:200])

        if not (raw or "").strip():
            fb = _fallback_from_tool(last_tool_name, last_tool_result)
            if fb:
                return await _deliver_final(fb, emit, stream_final)
            if iteration + 1 < max_iter:
                messages.append({
                    "role": "user",
                    "content": (
                        'Il modello ha risposto vuoto. Rispondi in italiano con '
                        '{"final": "la tua risposta qui"} — sintetica e utile.'
                    ),
                })
                continue
            return await _deliver_final(_EMPTY_REPLY_FALLBACK, emit, stream_final)

        parsed = _extract_json(raw)
        if not parsed and _looks_like_raw_tool_json(raw):
            parsed = _salvage_tool_call(raw)
            if parsed:
                logger.info("Tool JSON recuperato da risposta troncata: %s", parsed.get("tool"))

        if parsed and "final" in parsed:
            final = (parsed.get("final") or "").strip()
            if not final:
                fb = _fallback_from_tool(last_tool_name, last_tool_result)
                if fb:
                    return await _deliver_final(fb, emit, stream_final)
                continue
            fixed = await _apply_autofix_if_needed(
                user_text, emit, stream_final, bad_response=final,
            )
            if fixed:
                return fixed
            return await _deliver_final(final, emit, stream_final)

        if parsed and "tool" in parsed:
            tool_name = parsed["tool"]
            last_tool_name = tool_name
            tool_args = parsed.get("args") or {}
            reason = parsed.get("reason", "")

            if not tool_allowed(tool_name):
                result = (
                    f"Strumento '{tool_name}' non disponibile in modalità local-only "
                    "(Cursor/cloud disabilitati). Usa terminal, read_file, write_file, remember, recall."
                )
                last_tool_result = result
                await emit({"type": "state", "state": "ACTING"})
                await emit({"type": "tool_start", "tool": tool_name, "args": tool_args, "reason": reason})
                await emit({"type": "tool_end", "tool": tool_name, "result": result[:2000]})
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Risultato strumento '{tool_name}':\n{result}\n\n"
                        'Continua. Usa un altro strumento o rispondi con {"final": "..."}.'
                    ),
                })
                continue

            await emit({"type": "state", "state": "ACTING"})
            await emit({
                "type": "tool_start",
                "tool": tool_name,
                "args": tool_args,
                "reason": reason,
            })
            agent_id = await _emit_brain_agent(tool_name, tool_args, reason, emit)

            tool_context = {"on_event": emit} if tool_name in (
                "cursor_code", "self_develop", "mac_ssh", "autofix",
            ) else None
            result = await execute_tool(tool_name, tool_args, context=tool_context)
            last_tool_result = result

            await _emit_tool_side_effects(tool_name, tool_args, result, emit)

            await emit({
                "type": "tool_end",
                "tool": tool_name,
                "result": result[:2000],
            })
            await _emit_brain_agent_end(agent_id, emit)

            fixed = await _apply_autofix_if_needed(
                user_text,
                emit,
                stream_final,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=result,
            )
            if fixed:
                return fixed

            if tool_name == "remember":
                from backend.core.knowledge_graph import node_from_memory
                from backend.core.tools.memory_tool import _load, get_knowledge_stats
                mems = _load()
                if mems:
                    await emit({"type": "brain_node", "node": node_from_memory(mems[-1])})
                await emit({"type": "knowledge_update", **get_knowledge_stats()})
            elif tool_name in ("scan_folder", "add_knowledge_folder"):
                from backend.core.tools.memory_tool import _load, get_knowledge_stats
                from backend.core.knowledge_graph import node_from_memory
                mems = _load()
                tag = "knowledge-folder" if tool_name == "add_knowledge_folder" else "[indice-"
                new_nodes = [
                    e for e in mems
                    if tag in str(e.get("tags", [])) or tag in e.get("text", "")
                ]
                for entry in new_nodes[-6:]:
                    await emit({"type": "brain_node", "node": node_from_memory(entry)})
                await emit({"type": "knowledge_update", **get_knowledge_stats()})
                await emit({"type": "knowledge_grow", "amount": max(2, len(new_nodes[-6:]))})
            elif tool_name == "scan_mac_projects":
                from backend.core.tools.memory_tool import _load, get_knowledge_stats
                from backend.core.knowledge_graph import node_from_memory
                mems = _load()
                new_nodes = [
                    e for e in mems
                    if "knowledge-mac" in (e.get("tags") or []) or "[Mac/" in e.get("text", "")
                ]
                for entry in new_nodes[-8:]:
                    await emit({"type": "brain_node", "node": node_from_memory(entry)})
                await emit({"type": "knowledge_update", **get_knowledge_stats()})
                await emit({"type": "knowledge_grow", "amount": max(2, len(new_nodes[-8:]))})
            else:
                await emit({"type": "knowledge_grow", "amount": 1})

            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"Risultato strumento '{tool_name}':\n{result}\n\n"
                    'Continua. Usa un altro strumento o rispondi con {"final": "..."}.'
                ),
            })
            continue

        final = raw.strip()
        if not final:
            fb = _fallback_from_tool(last_tool_name, last_tool_result)
            return await _deliver_final(fb or _EMPTY_REPLY_FALLBACK, emit, stream_final)
        if _looks_like_raw_tool_json(final):
            return await _deliver_final(_EMPTY_REPLY_FALLBACK, emit, stream_final)
        return await _deliver_final(final, emit, stream_final)

    fallback = "Ho raggiunto il limite di operazioni per questa richiesta. Posso riprovare con un approccio più mirato."
    return await _deliver_final(fallback, emit, stream_final)


async def check_ollama() -> dict:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if r.status_code == 200:
                models = [m.get("name") for m in r.json().get("models", [])]
                return {"online": True, "models": models}
    except Exception as e:
        return {"online": False, "error": str(e)}
    return {"online": False}
