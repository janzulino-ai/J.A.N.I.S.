"""AI Auditor — confronto risposta locale (Ollama) vs teacher (Cursor/OpenRouter)."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.core.llm_lab.paths import lab_audits_dir

logger = logging.getLogger("JANIS.Lab.Audit")

_AUDIT_SYSTEM = (
    "Sei un auditor LLM per JANIS. Confronta la risposta STUDENT (modello locale) "
    "con la risposta TEACHER (riferimento). Rispondi SOLO con JSON valido, senza markdown."
)

_AUDIT_PROMPT = """Confronta STUDENT vs TEACHER per il prompt seguente.

## PROMPT
{prompt}

## TEACHER (riferimento)
{teacher_response}

## STUDENT (modello locale)
{student_response}

## METADATA
- student_model: {student_model}
- teacher_model: {teacher_model}

Restituisci JSON con questa struttura esatta:
{{
  "reasoning_gap": {{
    "missed_logic": ["..."],
    "hallucinations": ["..."],
    "skipped_steps": ["..."]
  }},
  "code_architecture": {{
    "elegance": "breve valutazione 1-2 frasi",
    "modularity": "breve valutazione 1-2 frasi",
    "critical_misses": ["..."]
  }},
  "prompt_tuned": "prompt ottimizzato per il modello locale, pronto all'uso",
  "modelfile": {{
    "temperature": 0.62,
    "top_p": 0.9,
    "system_prompt": "system prompt suggerito per il modello locale"
  }},
  "overall_score": 0
}}

overall_score: 0-100 (100 = STUDENT equivalente al TEACHER).
Liste vuote se nessun gap. Italiano conciso."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_audit_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        chunk = m.group(0).strip().strip("`")
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            pass
    return {}


def _default_audit() -> dict[str, Any]:
    return {
        "reasoning_gap": {
            "missed_logic": [],
            "hallucinations": [],
            "skipped_steps": [],
        },
        "code_architecture": {
            "elegance": "",
            "modularity": "",
            "critical_misses": [],
        },
        "prompt_tuned": "",
        "modelfile": {
            "temperature": 0.62,
            "top_p": 0.9,
            "system_prompt": "",
        },
        "overall_score": 0,
    }


def _normalize_audit(parsed: dict[str, Any]) -> dict[str, Any]:
    base = _default_audit()
    rg = parsed.get("reasoning_gap") or {}
    ca = parsed.get("code_architecture") or {}
    mf = parsed.get("modelfile") or {}

    base["reasoning_gap"] = {
        "missed_logic": list(rg.get("missed_logic") or []),
        "hallucinations": list(rg.get("hallucinations") or []),
        "skipped_steps": list(rg.get("skipped_steps") or []),
    }
    base["code_architecture"] = {
        "elegance": str(ca.get("elegance") or ""),
        "modularity": str(ca.get("modularity") or ""),
        "critical_misses": list(ca.get("critical_misses") or []),
    }
    base["prompt_tuned"] = str(parsed.get("prompt_tuned") or "")
    base["modelfile"] = {
        "temperature": float(mf.get("temperature") or 0.62),
        "top_p": float(mf.get("top_p") or 0.9),
        "system_prompt": str(mf.get("system_prompt") or ""),
    }
    try:
        base["overall_score"] = max(0, min(100, int(parsed.get("overall_score") or 0)))
    except (TypeError, ValueError):
        base["overall_score"] = 0
    return base


def audit_quality_score(audit: dict[str, Any]) -> float:
    """Heuristica 0-100 da risultato audit (per eval/promote)."""
    if not audit:
        return 0.0
    if "overall_score" in audit:
        try:
            return float(max(0, min(100, int(audit["overall_score"]))))
        except (TypeError, ValueError):
            pass
    score = 100.0
    rg = audit.get("reasoning_gap") or {}
    ca = audit.get("code_architecture") or {}
    score -= 8 * len(rg.get("missed_logic") or [])
    score -= 12 * len(rg.get("hallucinations") or [])
    score -= 5 * len(rg.get("skipped_steps") or [])
    score -= 15 * len(ca.get("critical_misses") or [])
    return max(0.0, min(100.0, score))


def _audit_path(audit_id: str) -> Path:
    return lab_audits_dir() / f"{audit_id}.json"


def list_audits(*, limit: int = 20) -> list[dict[str, Any]]:
    root = lab_audits_dir()
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict] = []
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id") or path.stem,
                "created_at": data.get("created_at"),
                "student_model": data.get("student_model"),
                "teacher_model": data.get("teacher_model"),
                "overall_score": (data.get("audit") or {}).get("overall_score"),
                "judge_provider": data.get("judge_provider"),
            })
        except Exception:
            continue
    return out


def load_audit(audit_id: str) -> dict[str, Any] | None:
    path = _audit_path(audit_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_audit(record: dict[str, Any]) -> Path:
    audit_id = record["id"]
    path = _audit_path(audit_id)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def _judge_audit(
    prompt: str,
    *,
    teacher_response: str,
    student_response: str,
    student_model: str,
    teacher_model: str,
) -> tuple[dict[str, Any], str]:
    from backend.core.llm_router import chat as llm_chat

    user_content = _AUDIT_PROMPT.format(
        prompt=prompt.strip(),
        teacher_response=teacher_response.strip(),
        student_response=student_response.strip(),
        student_model=student_model,
        teacher_model=teacher_model,
    )
    raw, provider = await llm_chat([
        {"role": "system", "content": _AUDIT_SYSTEM},
        {"role": "user", "content": user_content},
    ])
    parsed = _normalize_audit(_parse_audit_json(raw))
    if not parsed.get("prompt_tuned") and raw:
        parsed["prompt_tuned"] = prompt.strip()
    return parsed, provider


async def audit_responses(
    *,
    prompt: str,
    teacher_response: str,
    student_response: str,
    student_model: str | None = None,
    teacher_model: str | None = None,
    run_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Confronta STUDENT vs TEACHER, salva audit strutturato su disco."""
    prompt = (prompt or "").strip()
    teacher_response = (teacher_response or "").strip()
    student_response = (student_response or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt obbligatorio"}
    if not teacher_response:
        return {"ok": False, "error": "teacher_response obbligatorio"}
    if not student_response:
        return {"ok": False, "error": "student_response obbligatorio"}

    student_model = student_model or settings.OLLAMA_MODEL
    teacher_model = teacher_model or "teacher"

    audit_id = uuid.uuid4().hex[:12]
    judge_error: str | None = None
    judge_provider = "none"
    audit_body = _default_audit()

    try:
        audit_body, judge_provider = await _judge_audit(
            prompt,
            teacher_response=teacher_response,
            student_response=student_response,
            student_model=student_model,
            teacher_model=teacher_model,
        )
    except Exception as e:
        judge_error = str(e)[:300]
        logger.warning("Audit judge fallito: %s", e)

    quality = audit_quality_score(audit_body)
    record: dict[str, Any] = {
        "id": audit_id,
        "created_at": _now(),
        "prompt": prompt[:4000],
        "teacher_response": teacher_response[:8000],
        "student_response": student_response[:8000],
        "student_model": student_model,
        "teacher_model": teacher_model,
        "run_id": run_id,
        "tags": tags or [],
        "judge_provider": judge_provider,
        "judge_error": judge_error,
        "audit": audit_body,
        "quality_score": quality,
    }
    path = _save_audit(record)
    # W7c: audit debole → ticket lab/safe
    try:
        if quality < float(getattr(settings, "LAB_PROMOTE_MIN_SCORE", 60)):
            from backend.core.orchestrator.board import create_ticket

            create_ticket(
                f"[lab-audit] quality={quality:.0f} id={audit_id}",
                kind="lab",
                priority=3,
                detail=f"prompt={prompt[:400]}\nscore={quality}\npath={path}",
            )
    except Exception:
        logger.debug("lab audit→ticket skip", exc_info=True)
    return {
        "ok": judge_error is None,
        "audit_id": audit_id,
        "path": str(path),
        "judge_provider": judge_provider,
        "quality_score": quality,
        "audit": audit_body,
        "error": judge_error,
    }
