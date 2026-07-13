#!/usr/bin/env python3
"""Rename JANICE → JANIS in packages/brain (content + selective filenames)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "packages" / "brain"
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "data"}
TEXT_EXT = {
    ".py", ".js", ".css", ".html", ".md", ".json", ".jsonl", ".txt", ".yml", ".yaml",
    ".ini", ".toml", ".ps1", ".sh", ".mjs", ".env", ".example", ".gitignore",
}
REPLACEMENTS = [
    ("JANICE", "JANIS"),
    ("Janice", "Janis"),
    ("janice", "janis"),
    ("Just Analyzing Networks, Intelligence, Communication & Execution",
     "Just Another Neuralgic Improving Server"),
]


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def main() -> None:
    renamed_files = 0
    edited_files = 0
    for path in sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if should_skip(path):
            continue
        if path.is_file() and "janice" in path.name.lower():
            new_name = path.name.replace("janice", "janis").replace("JANICE", "JANIS")
            if new_name != path.name:
                dest = path.with_name(new_name)
                path.rename(dest)
                path = dest
                renamed_files += 1
        if path.is_file() and path.suffix.lower() in TEXT_EXT:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            new = text
            for old, new_val in REPLACEMENTS:
                new = new.replace(old, new_val)
            if new != text:
                path.write_text(new, encoding="utf-8")
                edited_files += 1
    print(f"Renamed files: {renamed_files}, edited: {edited_files}")


if __name__ == "__main__":
    main()
