"""Test sicurezza path e comandi."""
import os
import tempfile

import pytest

from backend.config import settings
from backend.core.security import resolve_workspace_path, validate_path, validate_terminal_command


def test_block_destructive_command():
    with pytest.raises(PermissionError):
        validate_terminal_command("format c:")


def test_allow_safe_command():
    validate_terminal_command("dir")


def test_path_outside_workspace():
    with pytest.raises(PermissionError):
        resolve_workspace_path("C:\\Windows\\System32")


def test_validate_path_inside_workspace(tmp_path, monkeypatch):
    ws = str(tmp_path / "workspace")
    os.makedirs(ws)
    monkeypatch.setattr(settings, "JANIS_WORKSPACE", ws)
    inner = os.path.join(ws, "progetto", "file.txt")
    os.makedirs(os.path.dirname(inner))
    resolved = validate_path(inner)
    assert resolved.startswith(ws)
