"""Test stabilità tool self_develop."""
from backend.core.self_dev import ensure_fleet_state, save_state
from backend.core.tools.self_develop import self_develop


def _reset_state():
    save_state({
        "active_project": "fleet",
        "phase": 0,
        "phase_label": "test",
        "decisions": {},
        "open_questions": [
            {
                "id": "first_tool",
                "question": "Primo tool remoto?",
                "options": ["terminal", "filesystem", "browser"],
            },
        ],
    })


async def test_record_decision_int_question_id():
    _reset_state()
    result = await self_develop({"action": "record_decision", "question_id": 4, "answer": "terminal"})
    assert "Decisione registrata [first_tool]" in result
    assert "terminal" in result
    state = ensure_fleet_state()
    assert state["decisions"]["first_tool"]["answer"] == "terminal"


async def test_record_decision_str_question_id():
    _reset_state()
    result = await self_develop(
        {"action": "record_decision", "question_id": "first_tool", "answer": "browser"}
    )
    assert "Decisione registrata [first_tool]" in result
    state = ensure_fleet_state()
    assert state["decisions"]["first_tool"]["answer"] == "browser"
