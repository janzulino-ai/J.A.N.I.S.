"""Test sandbox isolato per candidati Tech Scout."""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from backend.core.evolve_paths import sandbox_dir
from backend.core.tech_scout.discover import save_candidate

logger = logging.getLogger("JANIS.Scout.Sandbox")

SANDBOX_TIMEOUT = 120


async def run_sandbox_test(candidate_id: str) -> dict:
    from backend.core.tech_scout.discover import list_candidates

    cand = next((c for c in list_candidates() if c.get("id") == candidate_id), None)
    if not cand:
        return {"ok": False, "error": "Candidato non trovato"}

    cand["status"] = "testing"
    save_candidate(cand)
    work = sandbox_dir() / candidate_id
    work.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []

    source = cand.get("source")
    name = cand.get("name") or candidate_id

    if source == "pypi":
        steps.append(await _run_step(f"pip install {name}", ["pip", "install", "--target", str(work / "pkg"), name]))
        steps.append(await _run_step("import check", ["python3", "-c", f"import {name.replace('-', '_')}; print('ok')"]))
    elif source in ("github", "watchlist") and cand.get("url"):
        if work.exists() and any(work.iterdir()):
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True, exist_ok=True)
        url = cand["url"]
        if "github.com" in url:
            clone_url = url if url.endswith(".git") else f"{url}.git"
            steps.append(await _run_step("git clone", ["git", "clone", "--depth", "1", clone_url, str(work / "repo")]))

    passed = sum(1 for s in steps if s.get("ok"))
    result = {
        "ok": passed == len(steps) if steps else False,
        "steps": steps,
        "partial": 0 < passed < len(steps) if steps else False,
    }
    cand["sandbox_result"] = result
    cand["status"] = "tested" if result["ok"] else ("partial" if result.get("partial") else "rejected")
    save_candidate(cand)
    return result


async def _run_step(label: str, cmd: list[str]) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)
        ok = proc.returncode == 0
        return {
            "step": label,
            "ok": ok,
            "exit_code": proc.returncode,
            "stdout": (out.decode(errors="replace") or "")[:500],
            "stderr": (err.decode(errors="replace") or "")[:300],
        }
    except asyncio.TimeoutError:
        return {"step": label, "ok": False, "error": "timeout"}
    except Exception as e:
        return {"step": label, "ok": False, "error": str(e)}


async def cleanup_old_sandboxes(max_age_hours: int = 24) -> int:
    import time
    root = sandbox_dir()
    if not root.exists():
        return 0
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    for p in root.iterdir():
        if p.is_dir() and p.stat().st_mtime < cutoff:
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
    return removed
