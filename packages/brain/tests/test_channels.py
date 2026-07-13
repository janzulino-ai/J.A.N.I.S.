"""Test gateway canali."""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(mem_dir)
        monkeypatch.setenv("MEMORY_DIR", mem_dir)
        from backend.config import settings

        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)
        monkeypatch.setattr(settings, "CHANNELS_ENABLED", True)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
        from backend.main import app

        from fastapi.testclient import TestClient

        yield TestClient(app)


def test_channels_status(client):
    r = client.get("/api/channels/status")
    assert r.status_code == 200
    data = r.json()
    assert "telegram" in data
    assert "whatsapp" in data


def test_whatsapp_inbound_accepts_payload(client, monkeypatch):
    async def fake_process(text, on_event=None, stream_final=False):
        return "ok test"

    monkeypatch.setattr("backend.core.brain.process_message", fake_process)
    r = client.post(
        "/api/channels/whatsapp/inbound",
        json={"from_id": "393331234567@c.us", "text": "ciao", "mentioned": True},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
