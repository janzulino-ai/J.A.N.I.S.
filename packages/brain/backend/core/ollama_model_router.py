"""Selezione modello Ollama — probe, test, scelta per task."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger("JANIS.OllamaModels")

_PROBE_PROMPT = "Rispondi solo: OK"
_PROBE_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_PROBE_TTL = 600.0  # 10 min

_EMBED_PATTERNS = ("embed", "nomic-embed", "bge-", "mxbai-embed")

# Ordine preferenza per tier se non ancora probati
_TIER_HINTS: dict[str, tuple[str, ...]] = {
    "fast": ("1b", "2b", "3b", "phi", "tiny", "mini", "small"),
    "balanced": ("4b", "7b", "8b", "gemma", "mistral", "llama3"),
    "capable": ("12b", "13b", "14b", "32b", "70b", "gemma2:27", "qwen2.5:14", "gemma4"),
}


def _probe_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "ollama_model_probe.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_saved_probe() -> dict | None:
    f = _probe_path()
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _save_probe(data: dict) -> None:
    _probe_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def list_ollama_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if r.status_code != 200:
                return []
            return [
                m.get("name") for m in r.json().get("models", [])
                if m.get("name") and not _is_embed_model(m.get("name", ""))
            ]
    except Exception as e:
        logger.warning("list_ollama_models: %s", e)
        return []


def _is_embed_model(name: str) -> bool:
    n = name.lower()
    return any(p in n for p in _EMBED_PATTERNS)


def _tier_guess(name: str) -> str:
    n = name.lower()
    # Tag parametro nel nome (più affidabile del brand)
    size_fast = ("1b", ":1b", "2b", ":2b", "3b", ":3b", "phi", "tiny", "mini", "small")
    size_capable = ("70b", ":70b", "32b", ":32b", "27b", ":27b", "14b", ":14b", "12b", ":12b")
    if any(s in n for s in size_fast):
        return "fast"
    if any(s in n for s in size_capable):
        return "capable"
    for tier in ("capable", "balanced", "fast"):
        if any(h in n for h in _TIER_HINTS[tier]):
            return tier
    return "balanced"


async def probe_model(model: str, timeout: float = 25.0) -> dict[str, Any]:
    t0 = time.perf_counter()
    ok = False
    err = ""
    sample = ""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": _PROBE_PROMPT}],
                    "stream": False,
                    "options": {"num_predict": 8, "temperature": 0},
                },
            )
            r.raise_for_status()
            data = r.json()
            sample = (data.get("message") or {}).get("content", "")[:80]
            ok = bool(sample.strip())
    except Exception as e:
        err = str(e)[:200]
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "model": model,
        "ok": ok,
        "latency_ms": latency_ms,
        "tier_guess": _tier_guess(model),
        "sample": sample,
        "error": err or None,
        "probed_at": int(time.time()),
    }


async def probe_all_models(*, force: bool = False) -> dict[str, Any]:
    global _PROBE_CACHE
    now = time.time()
    if not force and _PROBE_CACHE["data"] and now - _PROBE_CACHE["ts"] < _PROBE_TTL:
        return _PROBE_CACHE["data"]

    models = await list_ollama_models()
    if not models and settings.OLLAMA_MODEL:
        models = [settings.OLLAMA_MODEL]

    results: list[dict] = []
    for m in models:
        results.append(await probe_model(m))

    working = [r for r in results if r.get("ok")]
    working.sort(key=lambda x: x.get("latency_ms") or 999999)

    by_tier: dict[str, str | None] = {"fast": None, "balanced": None, "capable": None}
    for r in working:
        tier = r.get("tier_guess") or "balanced"
        if not by_tier.get(tier):
            by_tier[tier] = r["model"]

    # fallback: fastest = fast, default = balanced, slowest/largest name = capable
    if working:
        if not by_tier["fast"]:
            by_tier["fast"] = working[0]["model"]
        if not by_tier["balanced"]:
            by_tier["balanced"] = working[min(1, len(working) - 1)]["model"]
        if not by_tier["capable"]:
            by_tier["capable"] = working[-1]["model"]
    # Preferenza latenza per tier fast (dopo probe reale)
    if len(working) >= 2:
        by_tier["fast"] = working[0]["model"]
        by_tier["capable"] = working[-1]["model"]
        if not by_tier.get("balanced"):
            by_tier["balanced"] = working[len(working) // 2]["model"]

    default = settings.OLLAMA_MODEL
    if default not in models and working:
        default = working[0]["model"]

    payload = {
        "ok": bool(working),
        "probed_at": int(now),
        "models_available": models,
        "results": results,
        "working": [r["model"] for r in working],
        "by_tier": by_tier,
        "default": default,
        "recommended": by_tier.get("balanced") or default,
    }
    _PROBE_CACHE = {"ts": now, "data": payload}
    _save_probe(payload)
    return payload


def classify_task(user_text: str, *, tool_loop: bool = False, iteration: int = 0) -> str:
    """fast | balanced | capable"""
    text = (user_text or "").lower()
    if tool_loop or iteration > 0:
        return "fast"  # tool follow-up: modello veloce
    heavy = (
        "implement", "analizz", "refactor", "codice", "autodev", "cursor",
        "roadmap", "scout", "fleet", "self_develop", "architett",
    )
    if any(k in text for k in heavy):
        return "capable"
    if len(text) > 400:
        return "balanced"
    if len(text) < 120:
        return "fast"
    return "balanced"


async def select_model(
    user_text: str = "",
    *,
    tool_loop: bool = False,
    iteration: int = 0,
    force_probe: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Sceglie modello Ollama testato per il task corrente."""
    probe = await probe_all_models(force=force_probe)
    tier = classify_task(user_text, tool_loop=tool_loop, iteration=iteration)
    by_tier = probe.get("by_tier") or {}
    working = probe.get("working") or []
    results = probe.get("results") or []

    if tier == "fast":
        model = by_tier.get("fast") or (working[0] if working else None)
    elif tier == "capable":
        cap = [r["model"] for r in results if r.get("ok") and r.get("tier_guess") == "capable"]
        model = cap[0] if cap else (working[-1] if working else None)
    else:
        model = by_tier.get(tier)

    model = model or by_tier.get(tier) or probe.get("recommended") or settings.OLLAMA_MODEL

    if model not in (probe.get("working") or probe.get("models_available") or []):
        model = probe.get("recommended") or settings.OLLAMA_MODEL

    meta = {
        "tier": tier,
        "selected": model,
        "probe_age_sec": int(time.time() - (probe.get("probed_at") or 0)),
        "working_count": len(probe.get("working") or []),
    }
    logger.info("Ollama model select tier=%s → %s", tier, model)
    return model, meta


async def get_probe_status() -> dict[str, Any]:
    saved = _load_saved_probe()
    if _PROBE_CACHE["data"]:
        return _PROBE_CACHE["data"]
    if saved:
        return saved
    return await probe_all_models()
