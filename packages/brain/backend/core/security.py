"""Validazione percorsi e comandi per strumenti JANIS."""
from __future__ import annotations

import os
import re
import shlex

from backend.config import settings

# Comandi / pattern pericolosi (case-insensitive)
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\brm\s+-r\s+-f\b",
    r"\bdel\s+/[fs]\b",
    r"\bformat\s+[a-z]:",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r":\(\)\s*\{",  # fork bomb
    r"\breg\s+(delete|add)\b",
    r"\bRemove-Item\s+.*-Recurse\s+-Force",
    r"\bStop-Computer\b",
    r"\bRestart-Computer\b",
    r">\s*/dev/sd",
    r"\bchmod\s+777\s+/\b",
    r"\bchown\s+.*\s+/\b",
]

_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS), re.IGNORECASE)


def workspace_root() -> str:
    return os.path.abspath(os.path.expanduser(settings.JANIS_WORKSPACE))


def validate_path(path: str, *, must_exist: bool = False) -> str:
    """Risolve e valida un percorso dentro JANIS_WORKSPACE."""
    if not path or not str(path).strip():
        raise PermissionError("Percorso vuoto non consentito.")
    base = workspace_root()
    target = os.path.abspath(os.path.expanduser(str(path).strip()))
    if not target.startswith(base):
        raise PermissionError(f"Percorso fuori workspace: {path}")
    if must_exist and not os.path.exists(target):
        raise FileNotFoundError(f"Percorso inesistente: {path}")
    return target


def resolve_workspace_path(path: str) -> str:
    """Alias retrocompatibile per validate_path."""
    return validate_path(path)


def validate_cwd(cwd: str | None) -> str:
    if not cwd:
        return workspace_root()
    return validate_path(cwd, must_exist=True)


def validate_terminal_command(command: str) -> None:
    """Blocca comandi shell pericolosi."""
    cmd = (command or "").strip()
    if not cmd:
        raise ValueError("Comando vuoto.")
    if _DANGEROUS_RE.search(cmd):
        raise PermissionError(f"Comando bloccato per sicurezza: {cmd[:120]}")
    # Blocca concatenazioni che nascondono comandi pericolosi
    for part in re.split(r"[;&|]", cmd):
        part = part.strip()
        if part and _DANGEROUS_RE.search(part):
            raise PermissionError(f"Comando bloccato (sotto-espressione): {part[:120]}")


def safe_basename(path: str) -> str:
    return os.path.basename(validate_path(path))


def scan_roots() -> list[str]:
    """Radici autorizzate per scan_folder (indice cartelle media)."""
    raw = (getattr(settings, "JANIS_SCAN_ROOTS", "") or "").strip()
    roots: list[str] = []
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part:
                roots.append(os.path.abspath(os.path.expanduser(part)))
    if not roots:
        movies = getattr(settings, "JANIS_MOVIES_PATH", "") or ""
        if movies.strip():
            roots.append(os.path.abspath(os.path.expanduser(movies.strip())))
        ws = workspace_root()
        if ws not in roots:
            roots.append(ws)
    # dedupe preservando ordine
    seen: set[str] = set()
    unique: list[str] = []
    for r in roots:
        key = os.path.normcase(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _is_under_root(target: str, root: str) -> bool:
    t = os.path.normcase(os.path.abspath(target))
    r = os.path.normcase(os.path.abspath(root))
    if t == r:
        return True
    return t.startswith(r + os.sep)


def validate_scan_path(path: str, *, must_exist: bool = False) -> str:
    """Valida percorso per scansione indice — solo sotto JANIS_SCAN_ROOTS."""
    if not path or not str(path).strip():
        raise PermissionError("Percorso vuoto non consentito.")
    target = os.path.abspath(os.path.expanduser(str(path).strip()))
    for root in scan_roots():
        if _is_under_root(target, root):
            if must_exist and not os.path.exists(target):
                raise FileNotFoundError(f"Percorso inesistente: {path}")
            return target
    allowed = ", ".join(scan_roots())
    raise PermissionError(
        f"Percorso fuori radici autorizzate per scansione: {path}. "
        f"Consentiti: {allowed}"
    )


_BLOCKED_LOCAL_PREFIXES = tuple(
    os.path.normcase(p)
    for p in (
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    )
)


def validate_local_folder(path: str, *, must_exist: bool = True) -> str:
    """Valida cartella su qualsiasi disco locale (per aggiunta via chat/UI)."""
    if not path or not str(path).strip():
        raise PermissionError("Percorso vuoto non consentito.")
    target = os.path.abspath(os.path.expanduser(str(path).strip()))
    norm = os.path.normcase(target)
    for blocked in _BLOCKED_LOCAL_PREFIXES:
        if norm == blocked or norm.startswith(blocked + os.sep):
            raise PermissionError(f"Cartella di sistema non consentita: {path}")
    if must_exist and not os.path.isdir(target):
        raise FileNotFoundError(f"Cartella inesistente: {path}")
    return target
