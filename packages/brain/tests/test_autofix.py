"""Test auto-correzione JANIS."""
from backend.core.autofix import (
    _classify_issue,
    looks_like_false_access_block,
    looks_like_tool_failure,
    looks_like_tool_success,
)


def test_detect_sandbox_hallucination():
    bad = "Non riesco ad accedere a H:\\Video, siamo in un sandbox."
    assert looks_like_false_access_block(bad, "impara H:\\Video")


def test_classify_false_path():
    issue = _classify_issue(
        "impara H:\\Video",
        None,
        None,
        "Non riesco ad accedere alla cartella H:\\Video",
    )
    assert issue == "false_path_block"


def test_self_develop_success_not_failure():
    result = (
        "Fase 2 delegata a Cursor Agent.\n\n"
        "Cursor Agent [finished]:\n"
        "**JANIS Fleet — Fase 2** è completata.\n"
        "probabilmente da un tentativo Cursor Agent fallito per errore bridge."
    )
    assert looks_like_tool_success("self_develop", result)
    assert not looks_like_tool_failure("self_develop", result)


def test_real_tool_failure_still_detected():
    assert looks_like_tool_failure("fleet_execute", "Fleet execute fallito: timeout")
    assert looks_like_tool_failure("add_knowledge_folder", "Errore permessi: accesso negato")
