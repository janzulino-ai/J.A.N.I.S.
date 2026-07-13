import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_presence_get():
    r = client.get("/api/presence")
    assert r.status_code == 200
    data = r.json()
    assert "device_id" in data
    assert "surface" in data


def test_presence_claim():
    r = client.post(
        "/api/presence/claim",
        json={"device_id": "test-widget", "surface": "widget", "follow_user": True},
    )
    assert r.status_code == 200
    assert r.json()["device_id"] == "test-widget"


def test_agents_sessions_list():
    r = client.get("/api/agents/sessions")
    assert r.status_code == 200
    assert "sessions" in r.json()


def test_widget_page():
    r = client.get("/widget")
    assert r.status_code == 200
