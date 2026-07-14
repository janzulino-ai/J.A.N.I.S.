"""Test AI Auditor LLM Lab."""
from __future__ import annotations

from backend.core.llm_lab.audit import (
    _normalize_audit,
    _parse_audit_json,
    audit_quality_score,
)


def test_parse_audit_json_fence():
    raw = """```json
{"reasoning_gap": {"missed_logic": ["x"], "hallucinations": [], "skipped_steps": []},
 "overall_score": 72}
```"""
    parsed = _parse_audit_json(raw)
    assert parsed["overall_score"] == 72
    assert parsed["reasoning_gap"]["missed_logic"] == ["x"]


def test_normalize_audit_defaults():
    norm = _normalize_audit({})
    assert norm["modelfile"]["temperature"] == 0.62
    assert norm["reasoning_gap"]["missed_logic"] == []


def test_audit_quality_score_from_gaps():
    audit = {
        "reasoning_gap": {"missed_logic": ["a"], "hallucinations": ["b"], "skipped_steps": []},
        "code_architecture": {"critical_misses": ["c"]},
    }
    score = audit_quality_score(audit)
    assert score == 100 - 8 - 12 - 15


def test_audit_quality_score_explicit():
    assert audit_quality_score({"overall_score": 85}) == 85.0
