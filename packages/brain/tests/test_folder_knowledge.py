"""Test conoscenza da cartelle (inventario)."""
import os
import tempfile

import pytest

from backend.config import settings
from backend.core.folder_knowledge import collect_inventory, get_knowledge_status, sync_enrichment_to_memory


@pytest.fixture
def knowledge_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        vault = os.path.join(tmp, "Vault")
        os.makedirs(vault)
        with open(os.path.join(vault, "note.md"), "w", encoding="utf-8") as f:
            f.write("# Progetto JANIS\nAssistente personale con second brain.")
        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        monkeypatch.setattr(settings, "JANIS_SCAN_ROOTS", vault)
        monkeypatch.setattr(settings, "MEMORY_DIR", os.path.join(tmp, "memory"))
        yield vault


def test_collect_inventory(knowledge_env):
    data = collect_inventory(knowledge_env)
    assert data["file_count"] >= 1
    assert any("note.md" in s.get("file", "") for s in data["snippets"])


def test_sync_enrichment_creates_memories(knowledge_env, monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_DIR", os.path.join(settings.JANIS_PROJECT_DIR, "memory"))
    enrichment = {
        "area": "Vault test",
        "summary": "Area di test per JANIS.",
        "clusters": [{"title": "Progetti", "insight": "JANIS è un assistente AI.", "tags": ["ai"], "related": []}],
    }
    created = sync_enrichment_to_memory(knowledge_env, enrichment)
    assert len(created) >= 1


def test_knowledge_status_empty():
    st = get_knowledge_status()
    assert "scan_roots" in st
