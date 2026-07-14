"""Auto-correzione JANIS: diagnostica, fix locale, escalation agente."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from backend.config import settings
from backend.core.capability_gaps import log_gap

logger = logging.getLogger("JANIS.Autofix")

EventCallback = Callable[[dict], Awaitable[None]]

_WIN_PATH_RE = re.compile(
    r'(?<![A-Za-z0-9])([A-Za-z]:\\(?:[^<>"|\n\r]+?))(?=[\s\.,;:!?\)]|$|")',
    re.IGNORECASE,
)

_HALLUCINATION_RE = re.compile(
    r"sandbox|non ho accesso|non riesco ad accedere|ambiente operativo|"
    r"copia (?:i |la )?(?:file|cartella)|drive [a-z]:.*non|permessi diretti",
    re.IGNORECASE,
)


def looks_like_false_memory_denial(text: str) -> bool:
    from backend.core.tools.memory_tool import looks_like_false_memory_denial as _denial

    return _denial(text)


@dataclass
class AutofixOutcome:
    fixed: bool
    message: str
    escalated: bool = False
    agent: str | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def _extract_paths(text: str) -> list[str]:
    return [p.rstrip("\\/.,") for p in _WIN_PATH_RE.findall(text or "")]


def looks_like_false_access_block(text: str, user_text: str = "") -> bool:
    if not text or not _HALLUCINATION_RE.search(text):
        return False
    if user_text and _extract_paths(user_text):
        return True
    return bool(_HALLUCINATION_RE.search(text))


_TOOL_SUCCESS_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "self_develop": (
        re.compile(r"^Fase \d+ delegata a Cursor Agent", re.I),
        re.compile(r"Decisione registrata \[", re.I),
        re.compile(r"Fase \d+ segnata completata", re.I),
        re.compile(r"Cursor Agent \[finished\]", re.I),
    ),
    "cursor_code": (
        re.compile(r"\[finished\]", re.I),
        re.compile(r"^Task completat", re.I),
    ),
    "add_knowledge_folder": (
        re.compile(r"^Cartella registrata", re.I),
        re.compile(r"^Appreso", re.I),
    ),
}

_TOOL_FAILURE_PREFIXES = (
    "errore",
    "fleet execute fallito",
    "invio whatsapp fallito",
    "ssh fallito",
    "compileall fallito",
    "✗",
)


def looks_like_tool_success(tool_name: str | None, tool_result: str | None) -> bool:
    """Esito positivo noto — non attivare autofix su narrativa con 'fallito'."""
    if not tool_result or not tool_name:
        return False
    patterns = _TOOL_SUCCESS_PATTERNS.get(tool_name, ())
    return any(p.search(tool_result) for p in patterns)


def looks_like_tool_failure(
    tool_name: str | None,
    tool_result: str | None,
    bad_response: str | None = None,
) -> bool:
    """Rileva fallimenti reali senza falsi positivi su testo narrativo."""
    del bad_response
    if looks_like_tool_success(tool_name, tool_result):
        return False
    if tool_result:
        first = tool_result.split("\n", 1)[0].strip().lower()
        if first.startswith(_TOOL_FAILURE_PREFIXES):
            return True
        if first.endswith(" fallito") or first.endswith(" fallita"):
            return True
    return False


async def _diag_path_access(path: str) -> dict[str, Any]:
    from backend.core.security import validate_local_folder

    try:
        resolved = validate_local_folder(path)
        return {"check": f"path:{path}", "ok": True, "detail": resolved}
    except Exception as e:
        return {"check": f"path:{path}", "ok": False, "detail": str(e)}


async def _diag_ollama() -> dict[str, Any]:
    from backend.core.brain import check_ollama

    o = await check_ollama()
    return {"check": "ollama", "ok": bool(o.get("online")), "detail": o}


def _classify_issue(
    user_text: str,
    tool_name: str | None,
    tool_result: str | None,
    bad_response: str | None,
) -> str:
    from backend.core.fleet_connectivity import looks_like_fleet_connection_issue

    combined = f"{tool_result or ''} {bad_response or ''}"
    if looks_like_fleet_connection_issue(user_text, combined):
        return "fleet_connection"
    paths = _extract_paths(user_text)
    if paths and (looks_like_false_access_block(bad_response or "") or "Errore permessi" in (tool_result or "")):
        return "false_path_block"
    if tool_name == "add_knowledge_folder" and (tool_result or "").startswith("Errore"):
        return "folder_learn_failed"
    if "ollama" in combined.lower() or "non raggiungibile" in combined.lower():
        return "ollama_offline"
    if tool_result and tool_result.startswith("Errore: strumento"):
        return "missing_tool"
    if bad_response and looks_like_false_access_block(bad_response, user_text):
        return "false_path_block"
    if tool_result and "JANIS_SCAN_ROOTS" in tool_result:
        return "scan_permission"
    if tool_result and tool_result.startswith("Errore"):
        return "tool_error"
    return "unknown"


async def _try_fix_path_block(paths: list[str], on_event: EventCallback | None) -> AutofixOutcome | None:
    if not paths:
        return None
    from backend.core.tools.registry import execute_tool

    path = paths[0]
    diag = await _diag_path_access(path)
    if not diag["ok"]:
        return AutofixOutcome(
            fixed=False,
            message=f"Diagnostica: la cartella `{path}` non è accessibile — {diag['detail']}",
            diagnostics=[diag],
        )

    if on_event:
        await on_event({"type": "tool_start", "tool": "add_knowledge_folder", "args": {"path": path}})
    result = await execute_tool("add_knowledge_folder", {"path": path, "learn": True})
    if on_event:
        await on_event({"type": "tool_end", "tool": "add_knowledge_folder", "result": result[:2000]})

    if result.startswith("Errore"):
        return AutofixOutcome(fixed=False, message=result, diagnostics=[diag])

    return AutofixOutcome(
        fixed=True,
        message=(
            f"Auto-correzione: il percorso `{path}` è accessibile. "
            f"Ho aggirato la risposta errata del modello e appreso la cartella.\n\n{result}"
        ),
        diagnostics=[diag],
    )


async def _try_fix_fleet_connection(on_event: EventCallback | None) -> AutofixOutcome:
    from backend.core.fleet_connectivity import (
        diag_fleet_hub,
        ensure_windows_firewall_rule,
        local_lan_ip,
    )

    port = settings.PORT
    diag = diag_fleet_hub(port)
    diagnostics: list[dict[str, Any]] = [diag]
    lan = local_lan_ip()
    hub_url = f"ws://{lan}:{port}/ws/fleet-node"

    if diag.get("localhost_only"):
        return AutofixOutcome(
            fixed=False,
            message=(
                f"Diagnostica Fleet: il backend ascolta solo su localhost (:{port}), "
                "quindi i nodi Mac ricevono WinError 10061 (Connection Refused).\n\n"
                "Correzione: imposta HOST=0.0.0.0 in .env e riavvia JANIS "
                "(launcher usa settings.HOST).\n\n"
                f"Dopo il riavvio, sul Mac:\n"
                f"FLEET_HUB_URL={hub_url} FLEET_NODE_ID=mac-mini python bridge/client.py"
            ),
            diagnostics=diagnostics,
        )

    if not diag.get("ok"):
        return AutofixOutcome(
            fixed=False,
            message=(
                f"Diagnostica Fleet: nessun listener su :{port}. "
                "Avvia JANIS sul coordinatore Windows, poi riprova la connessione bridge."
            ),
            diagnostics=diagnostics,
        )

    fw = ensure_windows_firewall_rule(port)
    diagnostics.append(fw)
    parts = [
        f"Auto-correzione Fleet: backend in ascolto su tutte le interfacce (:{port}).",
    ]
    if fw.get("ok"):
        parts.append("Regola firewall Windows verificata o aggiunta.")
    else:
        parts.append(f"Firewall: {fw.get('detail')}.")
    parts.append(
        f"Sul Mac Mini avvia il bridge:\n"
        f"FLEET_HUB_URL={hub_url} FLEET_NODE_ID=mac-mini python bridge/client.py"
    )
    return AutofixOutcome(fixed=True, message="\n\n".join(parts), diagnostics=diagnostics)


async def _try_fix_ollama(on_event: EventCallback | None) -> AutofixOutcome | None:
    from backend.core.ollama_service import ensure_ollama_running

    diag = await _diag_ollama()
    if diag["ok"]:
        return None
    ok = await ensure_ollama_running()
    diag2 = await _diag_ollama()
    if ok and diag2["ok"]:
        return AutofixOutcome(
            fixed=True,
            message="Auto-correzione: Ollama era offline — l'ho avviato. Riprova la richiesta.",
            diagnostics=[diag, diag2],
        )
    return None


async def _try_fix_scan_permission(
    user_text: str,
    tool_result: str | None,
    on_event: EventCallback | None,
) -> AutofixOutcome | None:
    """Aggiunge radici scan locali (WSL) invece di escalare a Cursor."""
    if not tool_result or "JANIS_SCAN_ROOTS" not in tool_result:
        return None

    from backend.core.folder_knowledge import add_knowledge_folder_path, persist_scan_roots
    from backend.core.security import mac_path_hint, scan_roots, windows_path_to_wsl
    from backend.core.tools.registry import execute_tool

    blocked = re.search(
        r"scansione:\s*(.+?)(?:\.\s*Consentiti|\.$)",
        tool_result,
        re.IGNORECASE,
    )
    candidates: list[str] = _extract_paths(user_text)
    if blocked:
        candidates.insert(0, blocked.group(1).strip())

    diagnostics: list[dict[str, Any]] = []
    for raw in candidates[:3]:
        mac_hint = mac_path_hint(raw)
        if mac_hint:
            return AutofixOutcome(
                fixed=False,
                message=mac_hint,
                diagnostics=[{"check": "mac_path", "ok": False, "detail": raw}],
            )

        paths_to_try = [raw]
        wsl = windows_path_to_wsl(raw)
        if wsl and wsl not in paths_to_try:
            paths_to_try.append(wsl)

        for p in paths_to_try:
            if not p or not os.path.isdir(p):
                diagnostics.append({"check": f"path:{p}", "ok": False, "detail": "non esiste su questo host"})
                continue
            try:
                if on_event:
                    await on_event({"type": "tool_start", "tool": "add_knowledge_folder", "args": {"path": p}})
                resolved = add_knowledge_folder_path(p)
                persist_scan_roots(scan_roots())
                if on_event:
                    await on_event({"type": "tool_end", "tool": "add_knowledge_folder", "result": resolved})
                scan_out = await execute_tool(
                    "scan_folder",
                    {"path": resolved, "category": "documents"},
                )
                if scan_out.startswith("Errore"):
                    diagnostics.append({"check": "scan_retry", "ok": False, "detail": scan_out[:300]})
                    continue
                return AutofixOutcome(
                    fixed=True,
                    message=(
                        f"Auto-correzione: aggiunta radice scan `{resolved}`.\n\n{scan_out}"
                    ),
                    diagnostics=diagnostics,
                )
            except Exception as e:
                diagnostics.append({"check": f"path:{p}", "ok": False, "detail": str(e)})

    allowed = ", ".join(scan_roots())
    return AutofixOutcome(
        fixed=False,
        message=(
            "Scansione bloccata — nessun path utente accessibile dal brain WSL.\n"
            f"Radici attuali: {allowed}\n"
            "Aggiungi in `.env`: JANIS_SCAN_ROOTS=/mnt/c/percorso/vault,..."
        ),
        diagnostics=diagnostics,
    )


async def _escalate_to_agent(
    issue_type: str,
    user_text: str,
    diagnostics: list[dict],
    tool_name: str | None,
    tool_result: str | None,
    on_event: EventCallback | None,
) -> AutofixOutcome:
    """Lancia agente Cursor o cursor_terminal se il fix locale non basta."""
    desc = (
        f"Autofix non risolto ({issue_type}). "
        f"Tool={tool_name}, esito={ (tool_result or '')[:300] }. "
        f"Utente: {user_text[:400]}"
    )
    gap = log_gap(
        desc,
        context=str(diagnostics)[:500],
        tool=tool_name or "autofix",
        severity="high",
        proposed_fix="Correzione codice JANIS o nuovo tool",
    )

    cursor_prompt = (
        f"Problema JANIS da correggere automaticamente.\n"
        f"Tipo: {issue_type}\n"
        f"Richiesta utente: {user_text}\n"
        f"Diagnostica: {diagnostics}\n"
        f"Tool coinvolto: {tool_name}\n"
        f"Errore: {(tool_result or '')[:800]}\n\n"
        f"Progetto: {settings.JANIS_PROJECT_DIR}\n"
        "Obiettivo: correggi il codice affinché JANIS non inventi limiti sandbox, "
        "usando gli strumenti già registrati (add_knowledge_folder, autofix). "
        "Modifica minima, test pytest se presenti."
    )

    from backend.core.cursor_memory import build_cursor_context

    memory_ctx = await build_cursor_context(cursor_prompt, settings.JANIS_PROJECT_DIR)
    if memory_ctx:
        cursor_prompt = f"{memory_ctx}\n{cursor_prompt}"

    escalated = bool(settings.CURSOR_API_KEY and settings.CURSOR_API_KEY.strip())
    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    if escalated and not (rt.paid_mode and rt.cursor_code_enabled):
        escalated = False

    if escalated:
        agent = "cursor_code"
        if on_event:
            await on_event({
                "type": "brain_agent",
                "action": "spawn",
                "id": f"agent-autofix-{gap['id'][:8]}",
                "label": "Autofix → Cursor",
                "tool": "cursor_code",
            })
        from backend.core.tools.registry import execute_tool

        agent_msg = await execute_tool(
            "cursor_code",
            {
                "prompt": cursor_prompt,
                "cwd": settings.JANIS_PROJECT_DIR,
                "memory_source": "autofix",
                "memory_decision": f"Escalation autofix per {issue_type}",
                "memory_gap": issue_type,
            },
            context={"on_event": on_event},
        )
    else:
        agent = None
        hints = []
        if not settings.CURSOR_API_KEY or not settings.CURSOR_API_KEY.strip():
            hints.append("CURSOR_API_KEY assente — auto-patch codice disabilitato (modalità local-first).")
        elif not (rt.paid_mode and rt.cursor_code_enabled):
            hints.append("Cursor code disabilitato in runtime — abilita paid_mode + cursor_code_enabled per auto-patch.")
        agent_msg = (
            f"Gap [{gap['id']}]: registrato per revisione.\n"
            + "\n".join(hints)
            + f"\nDiagnostica: {diagnostics}\n"
            + f"Proposta: {cursor_prompt[:400]}…"
        )

    agent_label = agent or "gap_registry"
    return AutofixOutcome(
        fixed=False,
        escalated=escalated,
        agent=agent_label,
        message=(
            "Ho analizzato il problema e il fix automatico locale non è bastato.\n"
            f"Ho registrato il gap `{gap['id']}`"
            + (f" e lanciato **{agent}**." if agent else ".")
            + f"\n\n{agent_msg[:2500]}"
        ),
        diagnostics=diagnostics,
    )


async def run_autofix(
    user_text: str,
    *,
    tool_name: str | None = None,
    tool_args: dict | None = None,
    tool_result: str | None = None,
    bad_response: str | None = None,
    on_event: EventCallback | None = None,
) -> AutofixOutcome:
    """
    Diagnostica → fix locale → escalation agente.
    """
    if on_event:
        await on_event({"type": "state", "state": "THINKING"})

    diagnostics: list[dict[str, Any]] = []
    issue = _classify_issue(user_text, tool_name, tool_result, bad_response)
    paths = _extract_paths(user_text)

    logger.info("Autofix issue=%s paths=%s tool=%s", issue, paths, tool_name)

    if looks_like_tool_success(tool_name, tool_result):
        return AutofixOutcome(
            fixed=False,
            message="Nessun intervento: l'ultimo strumento ha avuto esito positivo.",
            diagnostics=diagnostics,
        )

    if issue in ("false_path_block", "folder_learn_failed") and paths:
        for p in paths[:2]:
            diagnostics.append(await _diag_path_access(p))
        outcome = await _try_fix_path_block(paths, on_event)
        if outcome and outcome.fixed:
            if on_event:
                await on_event({"type": "knowledge_grow", "amount": 2})
            return outcome

    if issue == "ollama_offline":
        diagnostics.append(await _diag_ollama())
        outcome = await _try_fix_ollama(on_event)
        if outcome and outcome.fixed:
            return outcome

    if issue == "fleet_connection":
        outcome = await _try_fix_fleet_connection(on_event)
        diagnostics.extend(outcome.diagnostics)
        return outcome

    if issue == "scan_permission" or (tool_name == "scan_folder" and tool_result and "JANIS_SCAN_ROOTS" in tool_result):
        outcome = await _try_fix_scan_permission(user_text, tool_result, on_event)
        if outcome:
            if outcome.fixed and on_event:
                await on_event({"type": "knowledge_grow", "amount": 2})
            if outcome.fixed or not settings.CURSOR_API_KEY:
                return outcome

    if tool_result:
        diagnostics.append({"check": "tool_result", "ok": False, "detail": tool_result[:500]})

    return await _escalate_to_agent(
        issue, user_text, diagnostics, tool_name, tool_result, on_event,
    )
