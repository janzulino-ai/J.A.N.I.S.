"""Test memoria."""
import os
import tempfile

import pytest

from backend.config import settings


@pytest.fixture
def mem_module(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(mem_dir)
        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)
        from backend.core.tools import memory_tool as mem
        yield mem


def test_memory_search_empty(mem_module):
    results = mem_module.search_memories("xyz-not-found-12345")
    assert isinstance(results, list)
    assert len(results) == 0


def test_memory_search_mac_tag(mem_module):
    mem = mem_module
    mem._save([
        {
            "id": "m1",
            "text": "[Mac/JCRM] CRM project",
            "tags": ["knowledge-mac", "mac", "jcrm"],
            "source": "janis",
            "timestamp": "2026-06-20T18:33:03",
        },
        {
            "id": "m2",
            "text": "[Mac Fleet] Fleet summary",
            "tags": ["mac-fleet", "knowledge-mac"],
            "source": "janis",
            "timestamp": "2026-06-20T18:33:03",
        },
        {
            "id": "u1",
            "text": "Preferenza utente",
            "tags": ["prefs"],
            "source": "user",
            "timestamp": "2026-06-19",
        },
    ])
    mac_hits = mem.search_memories("mac")
    assert len(mac_hits) == 2
    assert all("mac" in (e.get("tags") or []) or "knowledge-mac" in (e.get("tags") or []) for e in mac_hits)


def test_memory_context_for_brain(mem_module):
    mem = mem_module
    mem._save([
        {
            "id": "m1",
            "text": "[Mac/JCRM] CRM",
            "tags": ["knowledge-mac"],
            "source": "janis",
            "timestamp": "2026-06-20",
        },
    ])
    ctx = mem.get_memory_context_for_brain("si sono aggiunte conoscenze alla memoria?")
    assert ctx is not None
    assert "MEMORIA ATTIVA" in ctx
    assert "Conoscenza Mac" in ctx
    assert "JCRM" in ctx


@pytest.mark.asyncio
async def test_memory_status_tool(mem_module):
    mem = mem_module
    mem._save([
        {
            "id": "m1",
            "text": "[Mac Fleet] Test fleet",
            "tags": ["mac-fleet", "knowledge-mac"],
            "source": "janis",
            "timestamp": "2026-06-20",
        },
    ])
    result = await mem.memory_status({})
    assert "Memorie totali" in result
    assert "Conoscenza Mac" in result


def test_memory_load_save(mem_module):
    mem = mem_module
    mem._save([{"id": "t1", "text": "hello", "tags": [], "source": "user", "timestamp": "2026-01-01"}])
    entries = mem._load()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_answer_memory_query_directly(mem_module, monkeypatch):
    mem = mem_module
    mem._save([
        {
            "id": "m1",
            "text": "[Mac/JCRM] CRM project",
            "tags": ["knowledge-mac"],
            "source": "janis",
            "timestamp": "2026-06-20",
        },
    ])
    from backend.core import brain

    events = []

    async def emit(ev):
        events.append(ev)

    result = await brain._answer_memory_query_directly(
        "si sono aggiunte conoscenze alla tua memoria le vedi?",
        emit,
        False,
    )
    assert result is not None
    assert "memori" in result.lower()
    assert "JCRM" in result or "Mac" in result


def test_is_memory_query(mem_module):
    assert mem_module.is_memory_query("si sono aggiunte conoscenze alla memoria?")
    assert mem_module.is_memory_query("hai nuovo conoscenze parlamene")
    assert mem_module.is_memory_query("sono state caricate nella memoria persistente")
    assert mem_module.is_memory_query("cosa ricordi?")
    assert not mem_module.is_memory_query("ciao come stai")


def test_is_memory_write_not_query(mem_module):
    msg = "ok voglio agire sulle tue risposte e creare delle regole che tu possa ricordare"
    assert mem_module.is_memory_write_intent(msg)
    assert not mem_module.is_memory_query(msg)
    assert mem_module.is_memory_write_intent("ricorda: rispondi sempre in modo breve")
    assert mem_module.parse_inline_remember("ricorda: rispondi sempre in modo breve") == "rispondi sempre in modo breve"


def test_false_memory_denial(mem_module):
    assert mem_module.looks_like_false_memory_denial("No non vedo nulla usa remember")
    assert mem_module.looks_like_false_memory_denial("Non è un bug di codice È una limitazione architetturale")
    assert not mem_module.looks_like_false_memory_denial("Sì vedo 14 voci Mac")


@pytest.mark.asyncio
async def test_remember_deduplicates(mem_module):
    mem = mem_module
    r1 = await mem.remember({"text": "Il colore preferito è blu", "tags": ["prefs"]})
    assert "Memorizzato" in r1
    r2 = await mem.remember({"text": "Il colore preferito è blu", "tags": ["colori"]})
    assert "aggiornato" in r2.lower() or "duplicato" in r2.lower()
    assert len(mem._load()) == 1
