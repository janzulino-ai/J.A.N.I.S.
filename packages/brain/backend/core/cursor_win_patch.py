"""Compatibilità e fix per cursor-sdk su Windows (e token bridge).

Fix inclusi:
1. Windows: ``select`` su pipe stderr → ``_read_discovery`` con thread.
2. Bridge Node: token ``token_urlsafe`` può iniziare con ``-`` e il parser CLI
   lo scambia per un flag → ``Missing value for --tool-callback-auth-token``.
"""
from __future__ import annotations

import logging
import queue
import secrets
import threading

logger = logging.getLogger("JANIS.CursorWinPatch")

_applied_win = False
_auth_patched = False


def _safe_bridge_auth_token() -> str:
    """Token sicuro per argv del bridge (mai prefisso ``-``)."""
    while True:
        token = secrets.token_urlsafe(32)
        if token and not token.startswith("-"):
            return token


def _patch_bridge_auth_tokens() -> None:
    global _auth_patched
    if _auth_patched:
        return
    try:
        from cursor_sdk import _store_callback as sc
        from cursor_sdk import _tool_callback as tc

        tc._new_auth_token = _safe_bridge_auth_token  # type: ignore[attr-defined]
        sc._new_auth_token = _safe_bridge_auth_token  # type: ignore[attr-defined]
        _auth_patched = True
        logger.info("cursor-sdk patch auth token (no leading dash)")
    except Exception as e:  # noqa: BLE001
        logger.warning("Patch auth token cursor-sdk fallita: %s", e)


def _read_discovery_win(process, timeout):
    from cursor_sdk import _bridge as b

    if process.stderr is None:
        raise b.CursorSDKError("Bridge process stderr is unavailable")

    result_q: "queue.Queue[tuple[str, object]]" = queue.Queue()
    stderr_lines: list[str] = []

    def reader():
        try:
            for raw in iter(process.stderr.readline, ""):
                line = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
                stderr_lines.append(line)
                disc = b.parse_discovery_line(line)
                if disc is not None:
                    result_q.put(("ok", disc))
                    return
            result_q.put(("eof", None))
        except Exception as e:  # noqa: BLE001
            result_q.put(("err", e))

    threading.Thread(target=reader, daemon=True).start()
    try:
        kind, val = result_q.get(timeout=timeout)
    except queue.Empty:
        raise b.CursorSDKError("Timed out waiting for bridge discovery")

    if kind == "ok":
        return val
    if kind == "err":
        raise val  # type: ignore[misc]
    exit_code = process.poll()
    raise b.CursorSDKError(
        f"Bridge exited before discovery with status {exit_code}: " + "".join(stderr_lines)
    )


def reset_cursor_bridge() -> None:
    """Chiude il bridge/cliente di default dell'SDK.

    Su Windows il bridge globale cachato muore dopo la prima richiesta: la
    chiamata successiva trova ``connection refused`` (WinError 10061). Forzando
    un teardown pulito, ogni invocazione Agent.prompt riparte da un bridge nuovo.
    """
    try:
        from cursor_sdk import _client as c

        c.close_default_client()
    except Exception as e:  # noqa: BLE001
        logger.debug("reset_cursor_bridge no-op: %s", e)


def apply_cursor_sdk_patches() -> None:
    """Patch obbligatorie prima di ogni Agent.prompt."""
    _patch_bridge_auth_tokens()
    _apply_windows_bridge_read()


def apply_windows_patch() -> bool:
    """Alias retrocompatibile."""
    apply_cursor_sdk_patches()
    return _applied_win


def _apply_windows_bridge_read() -> bool:
    global _applied_win
    import sys

    if sys.platform != "win32":
        return False
    if _applied_win:
        return True
    try:
        from cursor_sdk import _bridge as b

        b._read_discovery = _read_discovery_win  # type: ignore[attr-defined]
        _applied_win = True
        logger.info("cursor-sdk Windows patch (_read_discovery senza select)")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Impossibile applicare patch Windows cursor-sdk: %s", e)
        return False
