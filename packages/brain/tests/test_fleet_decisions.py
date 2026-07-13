"""Test cattura decisioni Fleet."""
from backend.core.fleet_decisions import try_capture_fleet_decision
from backend.core.self_dev import ensure_fleet_state, save_state


def _reset_state():
    save_state({
        "active_project": "fleet",
        "phase": 0,
        "phase_label": "test",
        "decisions": {},
        "open_questions": [
            {
                "id": "coordinator",
                "question": "coordinator?",
                "options": ["mac-mini", "windows"],
            },
            {
                "id": "network",
                "question": "network?",
                "options": ["lan", "tailscale"],
            },
        ],
        "completed_phases": [],
    })


def test_numbered_answer():
    _reset_state()
    r = try_capture_fleet_decision("1 windows")
    assert r is not None
    assert r["question_id"] == "coordinator"
    assert r["answer"] == "windows"
    assert r["remaining"] == 3


def test_natural_answer():
    _reset_state()
    try_capture_fleet_decision("1 windows")
    r = try_capture_fleet_decision("rete locale")
    assert r is not None
    assert r["question_id"] == "network"
    assert r["answer"] == "lan"


def test_ensure_migrates_legacy():
    save_state({
        "active_project": "fleet",
        "phase": 0,
        "decisions": {
            "Coordinator Machine": {"answer": "windows", "at": "x", "note": ""},
        },
        "open_questions": [],
    })
    state = ensure_fleet_state()
    assert "coordinator" in state["decisions"]
    assert state["decisions"]["coordinator"]["answer"] == "windows"
