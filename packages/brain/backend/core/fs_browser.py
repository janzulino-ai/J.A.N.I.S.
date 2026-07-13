"""Esplora unità e cartelle del PC (Windows: tutti i dischi HDD/SSD)."""
from __future__ import annotations

import os
import string
import sys
from typing import Any

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes


_DRIVE_TYPES = {
    0: "unknown",
    1: "invalid",
    2: "removable",
    3: "fixed",
    4: "network",
    5: "cdrom",
    6: "ramdisk",
}


def _normalize_path(path: str) -> str:
    if not path or not str(path).strip():
        raise ValueError("Percorso vuoto")
    target = os.path.abspath(os.path.expanduser(str(path).strip()))
    if "\0" in target:
        raise PermissionError("Percorso non valido")
    return target


def list_drives() -> list[dict[str, Any]]:
    """Elenco unità disponibili (C:, D:, … su Windows)."""
    if sys.platform != "win32":
        home = os.path.expanduser("~")
        return [{
            "path": home,
            "label": "Home",
            "type": "fixed",
            "available": os.path.isdir(home),
        }]

    kernel32 = ctypes.windll.kernel32
    bitmask = kernel32.GetLogicalDrives()
    drives: list[dict[str, Any]] = []

    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask & (1 << i)):
            continue
        root = f"{letter}:\\"
        dtype = kernel32.GetDriveTypeW(root)
        label = _volume_label(root)
        available = os.path.isdir(root)
        drives.append({
            "path": root,
            "letter": letter,
            "label": label or f"Unità {letter}:",
            "type": _DRIVE_TYPES.get(dtype, "unknown"),
            "available": available,
        })

    drives.sort(key=lambda d: d.get("letter", ""))
    return drives


def _volume_label(root: str) -> str:
    if sys.platform != "win32":
        return root
    buf = ctypes.create_unicode_buffer(256)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        root, buf, 256, None, None, None, None, 0,
    )
    return buf.value.strip() if ok and buf.value else ""


def browse_directory(path: str | None = None) -> dict[str, Any]:
    """Elenca sottocartelle di un percorso (per selettore in Impostazioni)."""
    if path:
        current = _normalize_path(path)
    elif sys.platform == "win32":
        current = os.environ.get("SystemDrive", "C:") + "\\"
    else:
        current = os.path.expanduser("~")

    if not os.path.exists(current):
        raise FileNotFoundError(f"Percorso inesistente: {current}")
    if not os.path.isdir(current):
        current = os.path.dirname(current) or current

    parent = os.path.dirname(current.rstrip("\\/"))
    if sys.platform == "win32" and len(current) <= 3 and current[1:3] == ":\\":
        parent = None
    elif not parent or parent == current:
        parent = None

    entries: list[dict[str, Any]] = []
    try:
        names = os.listdir(current)
    except PermissionError as e:
        raise PermissionError(f"Accesso negato: {current}") from e

    for name in sorted(names, key=str.lower):
        if name in (".", ".."):
            continue
        full = os.path.join(current, name)
        try:
            is_dir = os.path.isdir(full)
        except OSError:
            continue
        if not is_dir:
            continue
        entries.append({
            "name": name,
            "path": full,
            "is_dir": True,
        })

    return {
        "path": current,
        "parent": parent,
        "entries": entries,
    }
