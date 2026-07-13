"""Test persistenza chat."""
import os
import tempfile

import pytest

from backend.config import settings


@pytest.fixture
def chat_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        chat_dir = os.path.join(tmp, "chat")
        os.makedirs(chat_dir)
        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        from backend.core import chat_store as cs
        cs.new_session()
        yield cs


def test_append_and_load(chat_env):
    cs = chat_env
    cs.append_message("user", "Ciao JANIS")
    cs.append_message("assistant", "Ciao!")
    msgs = cs.load_messages(limit=10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "Ciao!"


def test_get_history(chat_env):
    cs = chat_env
    sid = cs.current_session_id()
    cs.append_message("user", "test history")
    data = cs.get_history(sid)
    assert data["session_id"] == sid
    assert data["count"] == 1


def test_new_session_clears_active(chat_env):
    cs = chat_env
    old = cs.current_session_id()
    cs.append_message("user", "old")
    new = cs.new_session()
    assert new != old
    assert cs.load_messages() == []
