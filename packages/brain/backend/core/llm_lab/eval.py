"""Valutazione modello custom vs baseline Ollama."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from backend.config import settings
from backend.core.ollama_model_router import probe_model

logger = logging.getLogger("JANIS.Lab.Eval")

_EVAL_PROMPTS = [
    {"id": "ping", "prompt": "Rispondi solo: OK", "expect_any": ["ok", "OK"]},
    {
        "id": "identity",
        "prompt": "Chi sei? Una frase.",
        "expect_any": ["janis", "JANIS", "assistente"],
    },
    {
        "id": "language",
        "prompt": "Dimmi ciao in italiano.",
        "expect_any": ["ciao", "Ciao", "salve", "Salve"],
    },
]


async def _chat_model(model: str, prompt: str, timeout: float = 60.0) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 128, "temperature": 0.2},
                },
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("message") or {}).get("content", "")
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {"ok": True, "content": content, "latency_ms": latency_ms}
    except Exception as e:
        return {
            "ok": False,
            "content": "",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error": str(e)[:200],
        }


def _score_response(content: str, expect_any: list[str]) -> bool:
    if not content.strip():
        return False
    low = content.lower()
    return any(e.lower() in low for e in expect_any)


async def evaluate_model(
    model: str,
    *,
    baseline: str | None = None,
    audit: dict | None = None,
) -> dict[str, Any]:
    """Confronta modello candidato vs baseline su probe JANIS."""
    baseline = baseline or settings.LAB_EVAL_BASELINE or settings.OLLAMA_MODEL
    results: list[dict] = []
    candidate_score = 0
    baseline_score = 0
    total_latency_c = 0.0
    total_latency_b = 0.0

    for item in _EVAL_PROMPTS:
        cand = await _chat_model(model, item["prompt"])
        base = await _chat_model(baseline, item["prompt"])
        c_ok = cand.get("ok") and _score_response(cand.get("content", ""), item["expect_any"])
        b_ok = base.get("ok") and _score_response(base.get("content", ""), item["expect_any"])
        if c_ok:
            candidate_score += 1
        if b_ok:
            baseline_score += 1
        total_latency_c += cand.get("latency_ms") or 0
        total_latency_b += base.get("latency_ms") or 0
        results.append({
            "id": item["id"],
            "candidate_ok": c_ok,
            "baseline_ok": b_ok,
            "candidate_latency_ms": cand.get("latency_ms"),
            "baseline_latency_ms": base.get("latency_ms"),
            "candidate_sample": (cand.get("content") or "")[:120],
        })

    total = len(_EVAL_PROMPTS)
    cand_pct = round(100 * candidate_score / total, 1) if total else 0
    base_pct = round(100 * baseline_score / total, 1) if total else 0
    promote = candidate_score >= baseline_score and cand_pct >= settings.LAB_PROMOTE_MIN_SCORE

    result = {
        "ok": True,
        "model": model,
        "baseline": baseline,
        "candidate_score": candidate_score,
        "baseline_score": baseline_score,
        "candidate_pct": cand_pct,
        "baseline_pct": base_pct,
        "avg_latency_ms": round(total_latency_c / max(total, 1), 1),
        "baseline_avg_latency_ms": round(total_latency_b / max(total, 1), 1),
        "promote_recommended": promote,
        "results": results,
    }
    if audit:
        from backend.core.llm_lab.audit import audit_quality_score

        audit_score = audit_quality_score(audit)
        result["audit_score"] = audit_score
        if audit_score < settings.LAB_PROMOTE_MIN_SCORE:
            result["promote_recommended"] = False
    return result


async def quick_probe(model: str) -> dict:
    return await probe_model(model, timeout=45.0)
