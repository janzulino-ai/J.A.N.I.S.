"""Log locale usage LLM — costi, token, latenza (alternativa leggera a Langfuse)."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger("JANIS.LLMUsage")

# Stima USD per 1M token (approssimativa, modelli cheap)
_COST_PER_1M: dict[str, float] = {
    "openrouter": 0.15,
    "cursor": 2.0,
    "anthropic": 3.0,
    "openai": 2.5,
}


def _usage_path() -> Path:
    root = Path(settings.JANIS_PROJECT_DIR)
    p = root / "data" / "llm_usage.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> dict:
    p = _usage_path()
    if not p.exists():
        return {"date": date.today().isoformat(), "calls": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("date") != date.today().isoformat():
            return {"date": date.today().isoformat(), "calls": []}
        return data
    except (json.JSONDecodeError, OSError):
        return {"date": date.today().isoformat(), "calls": []}


def _save(data: dict) -> None:
    data["date"] = date.today().isoformat()
    _usage_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def estimate_cost_usd(
    provider: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_chars: int = 0,
) -> float:
    """Stima costo pre/post chiamata."""
    p = (provider or "ollama").lower()
    if p == "ollama" or p == "local":
        return 0.0
    tokens = prompt_tokens + completion_tokens
    if tokens <= 0 and total_chars > 0:
        tokens = max(1, total_chars // 4)
    rate = _COST_PER_1M.get(p, 0.2)
    return round((tokens / 1_000_000) * rate, 6)


def parse_openrouter_usage(data: dict) -> tuple[int, int, float]:
    usage = data.get("usage") or {}
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    cost = float(data.get("cost") or 0)
    if cost <= 0:
        cost = estimate_cost_usd("openrouter", prompt_tokens=pt, completion_tokens=ct)
    return pt, ct, cost


def record_call(
    provider: str,
    *,
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    session_id: str = "",
    blocked: bool = False,
) -> dict:
    """Registra chiamata e ritorna entry."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost_usd, 6),
        "latency_ms": round(latency_ms, 1),
        "session_id": session_id,
        "blocked": blocked,
    }
    data = _load()
    calls = data.setdefault("calls", [])
    calls.append(entry)
    if len(calls) > 500:
        data["calls"] = calls[-500:]
    _save(data)
    return entry


def summary_today() -> dict[str, Any]:
    """Aggregati giornalieri per /api/status e HUD."""
    data = _load()
    calls = data.get("calls") or []
    total_cost = 0.0
    total_latency = 0.0
    lat_count = 0
    by_provider: dict[str, dict] = defaultdict(lambda: {"calls": 0, "cost_usd": 0.0, "tokens": 0})

    for c in calls:
        if c.get("blocked"):
            continue
        prov = c.get("provider") or "unknown"
        cost = float(c.get("cost_usd") or 0)
        total_cost += cost
        if c.get("latency_ms"):
            total_latency += float(c["latency_ms"])
            lat_count += 1
        by_provider[prov]["calls"] += 1
        by_provider[prov]["cost_usd"] += cost
        by_provider[prov]["tokens"] += int(c.get("prompt_tokens") or 0) + int(c.get("completion_tokens") or 0)

    top_models: dict[str, int] = defaultdict(int)
    for c in calls:
        m = c.get("model") or c.get("provider") or "unknown"
        top_models[m] += 1
    sorted_models = sorted(top_models.items(), key=lambda x: -x[1])[:5]

    return {
        "calls_today": len(calls),
        "spent_today_usd": round(total_cost, 4),
        "avg_latency_ms": round(total_latency / lat_count, 1) if lat_count else 0,
        "by_provider": dict(by_provider),
        "top_models": [{"model": m, "calls": n} for m, n in sorted_models],
        "recent": calls[-10:],
    }
