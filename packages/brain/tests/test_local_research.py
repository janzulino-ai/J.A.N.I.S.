"""Test local research helpers (SearXNG mocked)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_run_local_research_mocked(monkeypatch):
    from backend.core import local_research as lr

    async def fake_search(query, *, limit=8):
        return [
            {
                "title": "Example",
                "url": "https://example.com",
                "content": "snippet",
                "engine": "test",
            }
        ]

    async def fake_fetch(url, *, max_chars=4000):
        return "page body about the topic"

    async def fake_synth(query, sources):
        return "Report con citazione [1].\n\nCitazioni:\n[1] https://example.com"

    monkeypatch.setattr(lr, "searx_search", fake_search)
    monkeypatch.setattr(lr, "fetch_page_text", fake_fetch)
    monkeypatch.setattr(lr, "ollama_synthesize", fake_synth)

    result = await lr.run_local_research("test query", fetch_pages=1, save=False)
    assert result["ok"] is True
    assert "Report" in result["report"]
    assert result["mode"] == "searxng+ollama"
