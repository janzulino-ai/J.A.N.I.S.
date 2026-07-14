"""Router LLM multi-provider: Ollama → Cursor (PRO) → OpenRouter (+ LiteLLM proxy opzionale)."""
from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator

import httpx

from backend.config import settings
from backend.core.llm_usage import estimate_cost_usd, parse_openrouter_usage, record_call
from backend.core.orchestrator.cost_router import cost_router
from backend.core.paid_capabilities import check_allowed, record_paid_usage
from backend.core.runtime_config import effective_reasoning_provider, get_runtime

logger = logging.getLogger("JANIS.LLMRouter")

_CLOUD = frozenset({"openrouter", "cursor"})


async def _ollama_chat(messages: list[dict]) -> tuple[str, dict]:
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.62, "num_ctx": 8192},
            },
        )
        r.raise_for_status()
        data = r.json()
        content = data.get("message", {}).get("content", "")
        latency = (time.perf_counter() - t0) * 1000
        usage = {
            "prompt_tokens": data.get("prompt_eval_count") or 0,
            "completion_tokens": data.get("eval_count") or 0,
            "cost_usd": 0.0,
            "latency_ms": latency,
            "model": settings.OLLAMA_MODEL,
        }
        return content, usage


async def _openrouter_chat(messages: list[dict]) -> tuple[str, dict]:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY non configurata")
    gate = check_allowed("openrouter")
    if not gate.get("ok"):
        raise RuntimeError(gate.get("error", "OpenRouter non consentito"))
    est = estimate_cost_usd("openrouter", total_chars=sum(len(m.get("content") or "") for m in messages))
    if not cost_router._budget_ok(est):
        raise RuntimeError("Budget giornaliero esaurito — OpenRouter bloccato")

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8001",
                "X-Title": "JANIS",
            },
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": messages,
                "temperature": 0.62,
            },
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        pt, ct, cost = parse_openrouter_usage(data)
        latency = (time.perf_counter() - t0) * 1000
        usage = {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "cost_usd": cost,
            "latency_ms": latency,
            "model": settings.OPENROUTER_MODEL,
        }
        cost_router.record_spend(cost)
        record_paid_usage("openrouter", cost)
        return content, usage


async def _cursor_chat(messages: list[dict]) -> tuple[str, dict]:
    gate = check_allowed("cursor", require_quality=True)
    if not gate.get("ok"):
        raise RuntimeError(gate.get("error", "Cursor non consentito"))
    est = gate.get("estimate_usd") or 0.05
    if not cost_router._budget_ok(est):
        raise RuntimeError("Budget insufficiente per Cursor")

    from backend.core.cursor_llm import cursor_chat

    rt = get_runtime()
    model = rt.cursor_reasoning_model or settings.CURSOR_MODEL
    t0 = time.perf_counter()
    content = await cursor_chat(messages, model)
    latency = (time.perf_counter() - t0) * 1000
    chars = sum(len(m.get("content") or "") for m in messages) + len(content or "")
    cost = estimate_cost_usd("cursor", total_chars=chars)
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": cost,
        "latency_ms": latency,
        "model": model,
    }
    cost_router.record_spend(cost)
    record_paid_usage("cursor", cost)
    return content, usage


async def _litellm_chat(messages: list[dict], model: str) -> tuple[str, dict]:
    """Proxy LiteLLM locale (:4000) — unifica provider con budget."""
    base = settings.LITELLM_PROXY_URL.rstrip("/")
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY or 'sk-janis-local'}"},
            json={"model": model, "messages": messages, "temperature": 0.62},
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage") or {}
        pt = int(usage_raw.get("prompt_tokens") or 0)
        ct = int(usage_raw.get("completion_tokens") or 0)
        cost = float(data.get("_janis_cost") or 0)
        if cost <= 0 and "ollama" not in model.lower():
            cost = estimate_cost_usd("openrouter", prompt_tokens=pt, completion_tokens=ct)
        latency = (time.perf_counter() - t0) * 1000
        usage = {"prompt_tokens": pt, "completion_tokens": ct, "cost_usd": cost, "latency_ms": latency, "model": model}
        if cost > 0:
            cost_router.record_spend(cost)
        return content, usage


def _build_chain(provider: str) -> list[str]:
    rt = get_runtime()
    p = (provider or "ollama").lower().strip()
    cloud_ok = cost_router.cloud_budget_available()

    if settings.LITELLM_PROXY_URL:
        if cloud_ok:
            return ["litellm"]
        return ["ollama"]

    if not rt.paid_mode:
        if p == "openrouter" and cloud_ok:
            return ["openrouter", "ollama"]
        if p == "auto":
            chain = ["ollama"]
            if settings.OPENROUTER_API_KEY and cloud_ok:
                chain.append("openrouter")
            return chain
        chain = ["ollama"]
        if settings.OPENROUTER_API_KEY and cloud_ok:
            chain.append("openrouter")
        return chain

    if p == "cursor" and cloud_ok:
        chain = ["cursor"]
        if rt.openrouter_when_paid and settings.OPENROUTER_API_KEY:
            chain.append("openrouter")
        chain.append("ollama")
        return chain
    if p == "openrouter" and cloud_ok:
        if settings.CURSOR_API_KEY:
            return ["openrouter", "cursor", "ollama"]
        return ["openrouter", "ollama"]
    if p == "auto":
        chain = []
        if settings.CURSOR_API_KEY and cloud_ok:
            chain.append("cursor")
        chain.append("ollama")
        if settings.OPENROUTER_API_KEY and cloud_ok:
            chain.append("openrouter")
        return chain or ["ollama"]
    chain = ["ollama"]
    if settings.OPENROUTER_API_KEY and cloud_ok:
        chain.append("openrouter")
    return chain


def _litellm_model_for_provider(p: str) -> str:
    if p == "ollama":
        return f"ollama/{settings.OLLAMA_MODEL}"
    if p == "openrouter":
        return f"openrouter/{settings.OPENROUTER_MODEL}"
    return settings.OLLAMA_MODEL


async def chat(messages: list[dict], *, session_id: str = "") -> tuple[str, str]:
    """Invia messaggi al provider attivo con catena di fallback e tracking costi."""
    provider = effective_reasoning_provider()
    chain = _build_chain(provider)

    last_err: Exception | None = None
    for p in chain:
        if p in _CLOUD and not cost_router.can_use_provider(p):
            logger.warning("Provider %s bloccato — budget esaurito", p)
            continue
        try:
            if p == "litellm":
                model = _litellm_model_for_provider(provider if provider != "auto" else "ollama")
                content, usage = await _litellm_chat(messages, model)
                prov_label = "litellm"
            elif p == "cursor":
                content, usage = await _cursor_chat(messages)
                prov_label = "cursor"
            elif p == "ollama":
                content, usage = await _ollama_chat(messages)
                prov_label = "ollama"
            elif p == "openrouter":
                content, usage = await _openrouter_chat(messages)
                prov_label = "openrouter"
            else:
                continue

            record_call(
                prov_label,
                model=usage.get("model", ""),
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cost_usd=float(usage.get("cost_usd") or 0),
                latency_ms=float(usage.get("latency_ms") or 0),
                session_id=session_id,
            )
            return content, prov_label
        except Exception as e:
            last_err = e
            logger.warning("Provider %s fallito: %s", p, e)
            record_call(p, blocked=True, session_id=session_id)
            continue

    raise RuntimeError(f"Tutti i provider LLM falliti: {last_err}")


async def chat_stream(messages: list[dict]) -> AsyncIterator[str]:
    """Stream da Ollama (Cursor/OpenRouter non streamati in v1)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.62, "num_ctx": 8192},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def get_active_provider() -> dict:
    """Stato provider attivo per UI."""
    rt = get_runtime()
    configured = effective_reasoning_provider()
    ollama_ok = False
    openrouter_ok = bool(settings.OPENROUTER_API_KEY)
    cursor_ok = bool(settings.CURSOR_API_KEY)
    litellm_ok = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    if settings.LITELLM_PROXY_URL:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                base = settings.LITELLM_PROXY_URL.rstrip("/").replace("/v1", "")
                for path in ("/health/liveliness", "/health", "/"):
                    r = await client.get(f"{base}{path}")
                    if r.status_code == 200:
                        litellm_ok = True
                        break
        except Exception:
            pass

    chain = _build_chain(configured)
    active = "none"
    for p in chain:
        if p == "litellm" and litellm_ok:
            active = "litellm"
            break
        if p == "ollama" and ollama_ok:
            active = "ollama"
            break
        if p == "cursor" and cursor_ok:
            active = "cursor"
            break
        if p == "openrouter" and openrouter_ok:
            active = "openrouter"
            break

    from backend.core.llm_usage import summary_today

    return {
        "configured": configured,
        "active": active,
        "paid_mode": rt.paid_mode,
        "reasoning_provider": rt.reasoning_provider if rt.paid_mode else configured,
        "cursor_reasoning_model": rt.cursor_reasoning_model,
        "ollama_online": ollama_ok,
        "openrouter_configured": openrouter_ok,
        "cursor_configured": cursor_ok,
        "litellm_proxy": bool(settings.LITELLM_PROXY_URL),
        "litellm_online": litellm_ok,
        "ollama_model": settings.OLLAMA_MODEL,
        "openrouter_model": settings.OPENROUTER_MODEL,
        "cursor_model": settings.CURSOR_MODEL,
        "fallback_chain": chain,
        "cloud_blocked": not cost_router.cloud_budget_available(),
        "llm_usage": summary_today(),
    }


def active_provider_label() -> str:
    provider = effective_reasoning_provider()
    if settings.LITELLM_PROXY_URL:
        return "litellm"
    if provider == "cursor" and settings.CURSOR_API_KEY:
        return "cursor"
    if provider == "openrouter" and settings.OPENROUTER_API_KEY:
        return "openrouter"
    return "ollama"
