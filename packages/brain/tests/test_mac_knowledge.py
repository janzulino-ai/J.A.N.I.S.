"""Test scansione progetti Mac (mock SSH)."""
import json
import os
import tempfile

import pytest

from backend.config import settings


@pytest.fixture
def mac_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        monkeypatch.setattr(settings, "MEMORY_DIR", os.path.join(tmp, "memory"))
        monkeypatch.setattr(settings, "MAC_SSH_ENABLED", True)
        monkeypatch.setattr(settings, "MAC_SSH_HOST", "mac-mini-di-janzu.local")
        yield tmp


@pytest.mark.asyncio
async def test_scan_mac_projects_mock(mac_env, monkeypatch):
    sample = [
        {
            "name": "JCRM",
            "path": "/Users/janzu/Documents/JCRM",
            "has_git": True,
            "has_cursor": True,
            "readme": "README.md",
            "stack_files": ["package.json", "requirements.txt"],
        },
        {
            "name": "JANIS",
            "path": "/Users/janzu/Documents/JANIS",
            "has_git": True,
            "has_cursor": False,
            "readme": "",
            "stack_files": ["requirements.txt"],
        },
    ]

    async def fake_ssh(command, cwd=None):
        return 0, json.dumps(sample), ""

    monkeypatch.setattr("backend.core.mac_knowledge.run_mac_ssh", fake_ssh)

    from backend.core.mac_knowledge import scan_mac_projects

    result = await scan_mac_projects()
    assert result["ok"] is True
    assert result["count"] == 2
    assert result["projects"][0]["name"] == "JCRM"


def test_parse_scan_json():
    from backend.core.mac_knowledge import _parse_scan_json

    raw = 'noise\n[{"name":"A","path":"/x/A","has_git":1,"has_cursor":0,"readme":"","stack_files":"go.mod"}]\n'
    projects = _parse_scan_json(raw)
    assert len(projects) == 1
    assert projects[0]["stack_files"] == ["go.mod"]


@pytest.mark.asyncio
async def test_sync_mac_enrichment(mac_env):
    from backend.core.mac_knowledge import sync_mac_enrichment_to_memory

    projects = [{"name": "JCRM", "path": "/Users/janzu/Documents/JCRM", "has_git": True, "has_cursor": True, "stack_files": ["package.json"]}]
    enrichment = {
        "summary": "Fleet Mac con progetti Cursor.",
        "projects": [{"name": "JCRM", "purpose": "CRM", "stack": "Node+Python", "tags": ["crm"], "related": ["JANIS"]}],
    }
    created = sync_mac_enrichment_to_memory(projects, enrichment)
    assert len(created) >= 1


def test_mac_context_includes_memory(mac_env):
    from backend.core.mac_knowledge import sync_mac_enrichment_to_memory, get_context_for_brain, save_state

    projects = [{"name": "JCRM", "path": "/Users/janzu/Documents/JCRM", "has_git": True, "has_cursor": True, "stack_files": ["Gemfile"]}]
    enrichment = {
        "summary": "Fleet Mac con progetti Cursor.",
        "projects": [{"name": "JCRM", "purpose": "CRM", "stack": "Ruby", "tags": ["crm"], "related": []}],
    }
    sync_mac_enrichment_to_memory(projects, enrichment)
    save_state({
        "projects": {p["path"]: {**p, "enriched_at": "2026-06-20T18:33:03"} for p in projects},
        "last_scan": "2026-06-20T18:32:43",
        "last_enriched": "2026-06-20T18:33:03",
    })

    ctx = get_context_for_brain("si sono aggiunte conoscenze alla memoria?")
    assert ctx is not None
    assert "PROGETTI MAC" in ctx
    assert "Conoscenza Mac in long_term.json" in ctx
    assert "JCRM" in ctx
