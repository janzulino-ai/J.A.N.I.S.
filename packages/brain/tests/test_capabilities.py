"""Capability Fabric + fallback nativi."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(mem_dir)
        monkeypatch.setenv("MEMORY_DIR", mem_dir)
        from backend.config import settings

        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)
        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        monkeypatch.setattr(settings, "JANIS_WORKSPACE", tmp)
        from backend.main import app

        yield TestClient(app)


def test_capabilities_api(client):
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["wave"] == 1
    assert data["summary"] in ("green", "amber", "red")
    ids = {c["id"] for c in data["capabilities"]}
    assert "code_search" in ids
    assert "doc_read" in ids
    assert "research" in ids
    assert "image_gen" in ids
    assert "media_api" in ids
    assert "voice" in ids
    for c in data["capabilities"]:
        assert c["status"] in ("green", "amber", "red")
        assert "e2e" in c
        assert "backend" in c
        # Verde implica E2E
        if c["status"] == "green":
            assert c["e2e"] is True


@pytest.mark.asyncio
async def test_native_code_search_fallback(tmp_path, monkeypatch):
    from backend.config import settings
    from backend.core.native_fallbacks import native_code_search

    sample = tmp_path / "hello_janis.py"
    sample.write_text("def hello_janis_marker():\n    return 42\n", encoding="utf-8")
    monkeypatch.setattr(settings, "JANIS_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", str(tmp_path))

    out = await native_code_search("hello_janis_marker", root=str(tmp_path))
    assert "hello_janis_marker" in out
    assert "[native:" in out


@pytest.mark.asyncio
async def test_native_doc_read_text(tmp_path):
    from backend.core.native_fallbacks import native_doc_read

    p = tmp_path / "note.md"
    p.write_text("# Titolo JANIS\ncontenuto prova\n", encoding="utf-8")
    out = await native_doc_read(str(p))
    assert "Titolo JANIS" in out
    assert "[native:text]" in out


def test_doctor_includes_fabric(client):
    r = client.get("/api/doctor")
    assert r.status_code == 200
    data = r.json()
    assert "fabric" in data
    ids = [c["id"] for c in data["checks"]]
    assert "capability_fabric" in ids
    # MCP senza session non deve essere trattato come required green
    mcp_checks = [c for c in data["checks"] if str(c["id"]).startswith("mcp:")]
    for c in mcp_checks:
        assert c.get("optional") is True
        if not c.get("session") and not c.get("integrated"):
            assert c.get("ok") is False or c.get("informational")
