"""Test API REST JANIS."""
from __future__ import annotations

import os
import tempfile

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
        from backend.main import app
        yield TestClient(app)


def test_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["service"] == "JANIS"


def test_orchestrator_status(client):
    r = client.get("/api/orchestrator/status")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["autonomy_level"] in ("L0", "L1", "L2", "L3")
    assert "agents" in data


def test_orchestrator_ticket_and_approvals(client):
    r = client.post(
        "/api/orchestrator/tickets",
        json={"title": "API smoke ticket", "kind": "safe", "priority": 3},
    )
    assert r.status_code == 200
    tid = r.json()["ticket"]["id"]
    r2 = client.get("/api/orchestrator/tickets", params={"status": "open"})
    assert r2.status_code == 200
    assert any(t["id"] == tid for t in r2.json()["tickets"])
    r3 = client.get("/api/orchestrator/approvals")
    assert r3.status_code == 200
    assert r3.json()["ok"] is True
    r4 = client.post("/api/orchestrator/notify", json={"title": "t", "body": "b"})
    assert r4.status_code == 200
    assert r4.json()["ok"] is True


def test_settings_get(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "ollama_model" in data
    assert "llm_active" in data


def test_setup_status(client):
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert "ollama_online" in r.json()


def test_projects(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert "projects" in r.json()


def test_memory_list(client):
    r = client.get("/api/memory?page=1&limit=10")
    assert r.status_code == 200
    assert "items" in r.json()


def test_clear(client):
    r = client.post("/api/clear")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "session_id" in r.json()


def test_chat_history(client):
    r = client.get("/api/chat/history")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert "messages" in data
    assert "sessions" in data


def test_memory_export(client):
    r = client.get("/api/memory/export")
    assert r.status_code == 200
    assert r.headers.get("content-disposition", "").startswith("attachment")
