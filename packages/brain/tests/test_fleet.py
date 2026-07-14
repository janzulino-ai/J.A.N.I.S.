"""Test Fleet Fase 1 — registro nodi."""
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
        monkeypatch.setattr(settings, "MAC_BRIDGE_TOKEN", "test-token")
        from backend.main import app
        yield TestClient(app)


def test_fleet_nodes_empty(client):
    r = client.get("/api/fleet/nodes")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["nodes_total"] == 0
    assert data["nodes_online"] == 0


def test_status_includes_fleet(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert "fleet" in r.json()


def test_import_main():
    from backend.main import app  # noqa: F401
    assert app.title == "JANIS"


def test_fleet_ws_register_and_heartbeat(client):
    with client.websocket_connect(
        "/ws/fleet-node?node_id=test-mac&token=test-token"
    ) as ws:
        hello_ack = ws.receive_json()
        assert hello_ack["type"] == "hello_ack"
        assert hello_ack["node_id"] == "test-mac"
        assert hello_ack["coordinator"] == "linux"

        ws.send_json({
            "type": "hello",
            "node_id": "test-mac",
            "hostname": "MacTest",
            "os": "darwin",
            "capabilities": ["terminal"],
        })
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        ws.send_json({"type": "heartbeat"})
        hb = ws.receive_json()
        assert hb["type"] == "heartbeat_ack"
        assert hb["node_id"] == "test-mac"

        status = client.get("/api/fleet/nodes").json()
        assert status["nodes_online"] == 1
        assert status["nodes"][0]["node_id"] == "test-mac"
        assert status["nodes"][0]["capabilities"] == ["terminal"]


def test_fleet_ws_rejects_bad_token(client):
    with client.websocket_connect(
        "/ws/fleet-node?node_id=bad&token=wrong"
    ) as ws:
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "token" in err["message"].lower()
