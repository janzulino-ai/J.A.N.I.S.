"""Test archivio e rielaborazione chat."""
import os
import tempfile

import pytest

from backend.config import settings


@pytest.fixture
def chat_module(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "chat"))
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(mem_dir)
        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)
        from backend.core import chat_store as cs
        cs.new_session()
        yield cs


@pytest.fixture
def mem_module(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(mem_dir)
        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)
        from backend.core.tools import memory_tool as mem
        yield mem


@pytest.mark.asyncio
async def test_reprocess_session_creates_summary(chat_module, mem_module):
    cs = chat_module
    mem = mem_module
    sid = "test-session-archive"
    cs.set_session(sid)
    cs.append_message("user", "ricorda: rispondi sempre in modo breve", session_id=sid)
    cs.append_message("assistant", "Ok, memorizzato.", session_id=sid)
    cs.append_message("user", "come funziona fleet?", session_id=sid)

    from backend.core.chat_archive import archive_stats, is_session_processed, reprocess_session

    assert not is_session_processed(sid)
    result = await reprocess_session(sid)
    assert result["ok"]
    assert result["message_count"] == 3
    assert result["remember_extracted"] >= 1
    assert is_session_processed(sid)
    stats = archive_stats()
    assert stats["processed"] >= 1
    entries = mem._load()
    assert any("chat-archive" in (e.get("tags") or []) for e in entries)
