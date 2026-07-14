"""Classificazione candidati: local | hybrid | cloud_only."""
from __future__ import annotations

import json
import re
from typing import Any

from backend.core.tech_scout.discover import save_candidate

_CLOUD_KEYWORDS = re.compile(
    r"openai|anthropic|cloud.?api|saas|paid|subscription|cursor\.com|openrouter",
    re.I,
)
_LOCAL_KEYWORDS = re.compile(
    r"self.?host|local|ollama|docker|on.?prem|offline|embedded|piper|whisper",
    re.I,
)
_HYBRID_KEYWORDS = re.compile(r"hybrid|fallback|optional.?cloud|lite.?llm", re.I)


def classify_candidate(candidate: dict) -> dict:
    text = " ".join([
        candidate.get("name") or "",
        candidate.get("description") or "",
        candidate.get("url") or "",
        " ".join(candidate.get("topics") or []),
    ])
    deployment = "local"
    cost_model = "free_selfhosted"
    if _CLOUD_KEYWORDS.search(text) and not _LOCAL_KEYWORDS.search(text):
        deployment = "cloud_only"
        cost_model = "pay_per_use"
    elif _HYBRID_KEYWORDS.search(text) or (_CLOUD_KEYWORDS.search(text) and _LOCAL_KEYWORDS.search(text)):
        deployment = "hybrid"
        cost_model = "freemium"

    capability_type = "general"
    lower = text.lower()
    for kind, keys in (
        ("llm_gateway", ("litellm", "llm", "openrouter")),
        ("vector_db", ("qdrant", "chroma", "vector", "embed")),
        ("monitoring", ("glances", "netdata", "prometheus")),
        ("channels", ("telegram", "whatsapp", "openclaw", "slack")),
        ("mcp", ("mcp", "model context")),
    ):
        if any(k in lower for k in keys):
            capability_type = kind
            break

    candidate.update({
        "deployment": deployment,
        "cost_model": cost_model,
        "capability_type": capability_type,
        "resource_estimate": {"ram_mb": 256, "disk_mb": 100},
        "enables": [capability_type],
    })
    if candidate.get("status") == "discovered":
        candidate["status"] = "classified"
    return save_candidate(candidate)


async def classify_with_llm(candidate: dict) -> dict:
    """Classificazione arricchita via LLM (opzionale)."""
    from backend.core.llm_router import chat

    prompt = f"""Classifica questo tool OSS per JANIS. Rispondi SOLO JSON:
{{"deployment":"local|hybrid|cloud_only","capability_type":"...","janis_gap_match":["..."]}}

Candidato: {json.dumps({k: candidate.get(k) for k in ('name','url','description')}, ensure_ascii=False)}"""
    try:
        raw, _ = await chat([
            {"role": "system", "content": "JSON only."},
            {"role": "user", "content": prompt},
        ])
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if m:
            parsed = json.loads(m.group(0))
            candidate.update({k: v for k, v in parsed.items() if k in (
                "deployment", "capability_type", "janis_gap_match",
            )})
    except Exception:
        pass
    return classify_candidate(candidate)
