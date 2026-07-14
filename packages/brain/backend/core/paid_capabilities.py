"""Catalogo CLI/API a pagamento — gate budget prima dell'esecuzione."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.core.orchestrator.cost_router import cost_router

logger = logging.getLogger("JANIS.PaidCapabilities")

CLOUD_PROVIDERS = frozenset({"openrouter", "cursor", "anthropic", "openai"})


@dataclass
class PaidCapability:
    name: str
    tier: str  # local | cheap | premium
    estimate_usd: float
    requires_key: str
    kind: str  # api | cli
    description: str = ""


DEFAULT_CATALOG: list[PaidCapability] = [
    PaidCapability("ollama", "local", 0.0, "", "api", "LLM locale gratuito"),
    PaidCapability("openrouter", "cheap", 0.002, "OPENROUTER_API_KEY", "api", "Fallback cloud pay-per-token"),
    PaidCapability("cursor", "premium", 0.05, "CURSOR_API_KEY", "api", "Cursor SDK reasoning/autodev"),
    PaidCapability("cursor_agent", "premium", 0.10, "CURSOR_API_KEY", "cli", "Cursor Agent CLI"),
    PaidCapability("anthropic_api", "cheap", 0.003, "ANTHROPIC_API_KEY", "api", "Anthropic API diretta"),
    PaidCapability("openai_api", "cheap", 0.003, "OPENAI_API_KEY", "api", "OpenAI API diretta"),
    PaidCapability("gh_cli", "local", 0.0, "GH_TOKEN", "cli", "GitHub CLI (gratis con token)"),
]


def _usage_log_path() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "paid_usage.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _has_key(env_name: str) -> bool:
    if not env_name:
        return True
    return bool(getattr(settings, env_name, "") or "")


def list_capabilities() -> list[dict]:
    out = []
    for c in DEFAULT_CATALOG:
        out.append({
            "name": c.name,
            "tier": c.tier,
            "estimate_usd": c.estimate_usd,
            "requires_key": c.requires_key,
            "kind": c.kind,
            "description": c.description,
            "key_present": _has_key(c.requires_key),
        })
    return out


def check_allowed(name: str, *, require_quality: bool = False) -> dict[str, Any]:
    """Verifica se capability è consentita dato budget e tier."""
    cap = next((c for c in DEFAULT_CATALOG if c.name == name), None)
    if not cap:
        return {"ok": False, "error": f"Capability sconosciuta: {name}"}
    if cap.requires_key and not _has_key(cap.requires_key):
        return {"ok": False, "error": f"Chiave mancante: {cap.requires_key}"}
    if cap.tier == "local":
        return {"ok": True, "tier": "local", "estimate_usd": 0.0}
    tier = cost_router.pick_tier(require_quality=require_quality, cloud_only=(cap.tier == "premium"))
    if tier == "local" and cap.tier != "local":
        remaining = cost_router.status().get("remaining_usd", 0)
        if remaining <= 0:
            return {"ok": False, "error": "Budget giornaliero esaurito", "tier": tier}
    if not cost_router._budget_ok(cap.estimate_usd):
        return {"ok": False, "error": "Budget insufficiente per stima chiamata", "remaining_usd": cost_router.status().get("remaining_usd")}
    return {"ok": True, "tier": tier, "estimate_usd": cap.estimate_usd, "capability": cap.name}


def record_paid_usage(name: str, usd: float, *, tool: str = "", session: str = "") -> None:
    cost_router.record_spend(usd)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "capability": name,
        "usd": round(usd, 6),
        "tool": tool,
        "session": session,
    }
    path = _usage_log_path()
    log: list = []
    if path.exists():
        try:
            log = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    log.append(entry)
    if len(log) > 300:
        log = log[-300:]
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Paid usage %s $%.4f", name, usd)


def register_from_scout(candidate: dict) -> None:
    """Aggiunge candidato cloud_only verificato al catalogo runtime."""
    if candidate.get("deployment") != "cloud_only":
        return
    path = Path(settings.JANIS_PROJECT_DIR) / "data" / "scout" / "paid_catalog_extra.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    extra: list = []
    if path.exists():
        try:
            extra = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            extra = []
    name = candidate.get("name") or candidate.get("id")
    if any(e.get("name") == name for e in extra):
        return
    extra.append({
        "name": name,
        "tier": "cheap",
        "estimate_usd": 0.01,
        "requires_key": candidate.get("requires_key", ""),
        "kind": "api",
        "description": candidate.get("url", ""),
        "from_scout": True,
    })
    path.write_text(json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")
