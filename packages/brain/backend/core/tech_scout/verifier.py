"""Checklist verifica candidati Tech Scout."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.core.llm_usage import estimate_cost_usd
from backend.core.orchestrator.cost_router import cost_router
from backend.core.paid_capabilities import check_allowed
from backend.core.tech_scout.discover import list_candidates, save_candidate


def _report_path(candidate_id: str) -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "scout" / "reports" / f"{candidate_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


async def verify_local(candidate: dict) -> dict:
    checks = []
    sb = candidate.get("sandbox_result") or {}
    checks.append({"name": "sandbox", "ok": sb.get("ok", False), "detail": f"{len(sb.get('steps') or [])} steps"})
    ram = (candidate.get("resource_estimate") or {}).get("ram_mb", 256)
    try:
        import psutil
        avail_mb = psutil.virtual_memory().available / (1024 * 1024)
        checks.append({"name": "ram", "ok": avail_mb > ram, "detail": f"{avail_mb:.0f}MB avail"})
    except Exception:
        checks.append({"name": "ram", "ok": True, "detail": "psutil n/a"})
    return _finalize(candidate, checks)


async def verify_hybrid(candidate: dict) -> dict:
    base = await verify_local(candidate)
    checks = base.get("checks") or []
    if candidate.get("requires_key"):
        gate = check_allowed(candidate.get("name", ""))
        checks.append({"name": "api_key", "ok": gate.get("ok", False), "detail": gate.get("error", "ok")})
    return _finalize(candidate, checks, report_id=base.get("candidate_id"))


async def verify_cloud(candidate: dict) -> dict:
    est = estimate_cost_usd("openrouter", total_chars=1000)
    budget_ok = cost_router._budget_ok(est)
    checks = [
        {"name": "cost_estimate", "ok": budget_ok, "detail": f"~${est:.4f}/call"},
        {"name": "budget", "ok": cost_router.cloud_budget_available(), "detail": cost_router.status()},
    ]
    return _finalize(candidate, checks)


async def verify_candidate(candidate_id: str) -> dict:
    cand = next((c for c in list_candidates() if c.get("id") == candidate_id), None)
    if not cand:
        return {"ok": False, "error": "Candidato non trovato"}
    dep = cand.get("deployment") or "local"
    if dep == "cloud_only":
        report = await verify_cloud(cand)
    elif dep == "hybrid":
        report = await verify_hybrid(cand)
    else:
        report = await verify_local(cand)
    return report


def _finalize(candidate: dict, checks: list[dict], report_id: str | None = None) -> dict:
    cid = report_id or candidate.get("id") or "?"
    passed = [c for c in checks if c.get("ok")]
    failed = [c for c in checks if not c.get("ok")]
    if len(passed) == len(checks) and checks:
        verdict = "pass"
        candidate["status"] = "verified"
    elif passed:
        verdict = "partial"
        candidate["status"] = "partial"
    else:
        verdict = "fail"
        candidate["status"] = "rejected"
    report = {
        "candidate_id": cid,
        "verdict": verdict,
        "checks": checks,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    _report_path(cid).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate["verification_report"] = report
    save_candidate(candidate)
    return {"ok": verdict in ("pass", "partial"), "verdict": verdict, "report": report}
