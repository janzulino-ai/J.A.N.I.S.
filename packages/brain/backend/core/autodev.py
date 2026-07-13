"""Auto-sviluppo JANIS: verifica ragionamento (Cursor) → auto-codice → validazione → auto-riavvio.

Pipeline completa del ciclo evolutivo:
1. reflect individua un problema (gap/proposta).
2. autodev fa verificare/ottimizzare il piano a un modello di ragionamento Cursor.
3. Cursor Agent applica la modifica al codice.
4. Validazione: backup → py_compile dell'intero backend → restore se rotto.
5. Auto-riavvio del backend dev (opzionale).

Sicurezza: ogni file toccato viene salvato in .autodev_backup prima del run;
se la validazione fallisce, si ripristina automaticamente.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.AutoDev")


def _project_dir() -> Path:
    return Path(settings.JANIS_PROJECT_DIR)


def _backup_dir() -> Path:
    p = _project_dir() / "data" / ".autodev_backup"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_CURSOR_FAIL_MARKERS = (
    "Errore Cursor Agent",
    "non configurato",
    "richiede modalità PRO",
    "disabilitato nelle opzioni",
    "non installato",
    "Timed out waiting for bridge",
    "WinError",
)


def _cursor_failed(output: str | None) -> bool:
    if not output:
        return True
    return any(m in output for m in _CURSOR_FAIL_MARKERS)


# --------------------------------------------------------------------------- #
# Validazione
# --------------------------------------------------------------------------- #
def validate_backend() -> tuple[bool, str]:
    """Compila tutti i .py del backend per intercettare errori di sintassi."""
    backend_dir = _project_dir() / "backend"
    proc = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(backend_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    ok = proc.returncode == 0
    out = (proc.stdout + "\n" + proc.stderr).strip()
    return ok, out or ("OK" if ok else "compileall fallito")


def _snapshot_files(files: list[str]) -> dict[str, Path]:
    """Copia i file indicati nel backup; ritorna mappa originale→backup."""
    mapping: dict[str, Path] = {}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for rel in files:
        src = _project_dir() / rel
        if src.exists():
            dst = _backup_dir() / f"{stamp}__{rel.replace('/', '_').replace(chr(92), '_')}"
            shutil.copy2(src, dst)
            mapping[rel] = dst
    return mapping


def _restore_files(mapping: dict[str, Path]) -> None:
    for rel, backup in mapping.items():
        dst = _project_dir() / rel
        try:
            shutil.copy2(backup, dst)
        except OSError as e:
            logger.error("Restore fallito per %s: %s", rel, e)


# --------------------------------------------------------------------------- #
# Verifica del ragionamento via Cursor (modelli PRO)
# --------------------------------------------------------------------------- #
async def verify_plan_with_cursor(task: str, hint_files: list[str]) -> str:
    """Fa verificare/ottimizzare il piano d'intervento a un modello di ragionamento Cursor."""
    if not settings.CURSOR_API_KEY:
        return ""
    from backend.core.cursor_llm import cursor_chat
    from backend.core.runtime_config import get_runtime

    rt = get_runtime()
    model = rt.cursor_reasoning_model or settings.CURSOR_MODEL
    files_ctx = "\n".join(f"- {f}" for f in hint_files) if hint_files else "(da individuare)"
    messages = [
        {
            "role": "system",
            "content": (
                "Sei un revisore tecnico senior. Verifica e ottimizza il piano di fix. "
                "Rispondi conciso: causa probabile, fix minimo e sicuro, rischi, file da toccare."
            ),
        },
        {
            "role": "user",
            "content": f"Task di correzione:\n{task}\n\nFile candidati:\n{files_ctx}",
        },
    ]
    try:
        return await cursor_chat(messages, model)
    except Exception as e:
        logger.warning("Verifica Cursor fallita: %s", e)
        return ""


# --------------------------------------------------------------------------- #
# Auto-codice via Cursor Agent
# --------------------------------------------------------------------------- #
async def autocode(
    task: str,
    *,
    files: list[str] | None = None,
    verify: bool = True,
    restart: bool = False,
    emit=None,
) -> dict:
    """Esegue il ciclo auto-codice completo su un task descritto.

    Ritorna dict con: ok, plan, cursor_output, validated, restored, restarted.
    """
    files = files or []
    result: dict = {
        "ok": False,
        "task": task,
        "plan": None,
        "cursor_output": None,
        "validated": False,
        "restored": False,
        "restarted": False,
        "ts": _now(),
    }

    async def _log(msg: str):
        logger.info(msg)
        if emit:
            await emit({"type": "autodev", "message": msg})

    if not settings.CURSOR_API_KEY:
        result["error"] = "CURSOR_API_KEY mancante — auto-codice richiede Cursor PRO."
        return result

    # 1. Verifica del piano con modello di ragionamento Cursor
    plan = ""
    if verify:
        await _log("Verifico il piano con un modello di ragionamento Cursor…")
        plan = await verify_plan_with_cursor(task, files)
        result["plan"] = plan or None

    # 2. Backup dei file candidati
    snapshot = _snapshot_files(files) if files else {}

    # 3. Auto-codice via Cursor Agent
    from backend.core.tools.cursor_agent import cursor_code

    prompt_parts = [
        "Applica una correzione di codice minima, sicura e mirata.",
        f"\nTASK:\n{task}",
    ]
    if plan:
        prompt_parts.append(f"\nPIANO VERIFICATO:\n{plan}")
    if files:
        prompt_parts.append("\nFILE COINVOLTI:\n" + "\n".join(f"- {f}" for f in files))
    prompt_parts.append(
        "\nModifica direttamente i file nel repository. "
        "Non rompere import o sintassi. Mantieni lo stile esistente. "
        "Non aggiungere commenti superflui."
    )
    prompt = "\n".join(prompt_parts)

    await _log("Avvio Cursor Agent per applicare la correzione…")
    ctx = {"on_event": emit} if emit else {}
    cursor_out = await cursor_code({"prompt": prompt, "cwd": str(_project_dir())}, context=ctx)
    result["cursor_output"] = (cursor_out or "")[:4000]

    if _cursor_failed(cursor_out):
        await _log("Cursor Agent non ha applicato modifiche — abort.")
        if snapshot:
            _restore_files(snapshot)
            result["restored"] = True
        result["error"] = f"Cursor non disponibile/fallito: {(cursor_out or '')[:300]}"
        return result

    # 4. Validazione
    await _log("Validazione: compilazione backend…")
    ok, detail = validate_backend()
    result["validate_detail"] = detail[:1000]
    if not ok:
        await _log("Validazione FALLITA — ripristino backup.")
        if snapshot:
            _restore_files(snapshot)
            result["restored"] = True
        result["error"] = f"Validazione fallita: {detail[:300]}"
        return result

    result["validated"] = True
    result["ok"] = True
    await _log("Validazione OK.")

    # 5. Auto-riavvio (opzionale)
    if restart:
        await _log("Auto-riavvio backend richiesto…")
        result["restarted"] = request_restart()

    return result


# --------------------------------------------------------------------------- #
# Auto-riavvio backend dev
# --------------------------------------------------------------------------- #
def request_restart() -> bool:
    """Riavvia il backend dev in un processo detached (Windows-friendly)."""
    try:
        script = _project_dir() / "dev" / "start_backend.py"
        if not script.exists():
            logger.error("start_backend.py non trovato per riavvio")
            return False
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(_project_dir()),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Riavvio backend avviato")
        return True
    except Exception as e:
        logger.error("Riavvio fallito: %s", e)
        return False


async def autocode_proposal(proposal_id: str, *, restart: bool = False, emit=None) -> dict:
    """Esegue auto-codice a partire da una proposta di reflect (accettandola)."""
    from backend.core.reflect import decide_proposal, list_proposals

    target = None
    for p in list_proposals():
        if p["id"] == proposal_id or p["id"].startswith(proposal_id):
            target = p
            break
    if not target:
        return {"ok": False, "error": f"Proposta {proposal_id} non trovata"}

    task = f"{target['title']}\n\n{target.get('detail', '')}"
    res = await autocode(task, files=target.get("files") or [], verify=True, restart=restart, emit=emit)
    if res.get("ok"):
        decide_proposal(target["id"], accept=True)
        res["proposal"] = target["id"]
    return res
