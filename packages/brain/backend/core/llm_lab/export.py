"""Export modello addestrato → Ollama Modelfile + create."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.Lab.Export")


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: float = 600.0) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "")[:2000],
            "stderr": (proc.stderr or "")[:1000],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def export_to_ollama(run_dir: str, *, model_name: str | None = None) -> dict:
    """Crea modello Ollama da adapter/merged in run_dir."""
    run = Path(run_dir)
    model_name = model_name or settings.LAB_OLLAMA_MODEL_NAME
    merged = run / "merged"
    adapter = run / "adapter"
    gguf = run / "model.gguf"

    # Script export nel run (generato da train_unsloth.py)
    export_result_path = run / "export_result.json"
    if export_result_path.exists():
        try:
            prev = json.loads(export_result_path.read_text(encoding="utf-8"))
            if prev.get("gguf") and Path(prev["gguf"]).exists():
                gguf = Path(prev["gguf"])
        except json.JSONDecodeError:
            pass

    modelfile = run / "Modelfile"
    base = settings.LAB_BASE_MODEL.split("/")[-1].replace("-bnb-4bit", "")

    if gguf.exists():
        modelfile.write_text(
            f'FROM {gguf}\n'
            f'PARAMETER temperature 0.7\n'
            f'PARAMETER num_ctx 4096\n'
            f'SYSTEM """Sei JANIS — assistente AI locale addestrato su conversazioni reali. '
            f'Rispondi in italiano, conciso e utile."""\n',
            encoding="utf-8",
        )
    elif merged.exists() and any(merged.iterdir()):
        modelfile.write_text(
            f'FROM {merged}\n'
            f'PARAMETER temperature 0.7\n'
            f'PARAMETER num_ctx 4096\n'
            f'SYSTEM """Sei JANIS — assistente AI locale. Rispondi in italiano."""\n',
            encoding="utf-8",
        )
    elif adapter.exists() and any(adapter.iterdir()):
        # Ollama non importa LoRA direttamente — serve merge/GGUF
        return {
            "ok": False,
            "error": "Solo adapter LoRA presente — eseguire merge/GGUF prima dell'import Ollama",
            "adapter": str(adapter),
        }
    else:
        return {"ok": False, "error": "Nessun artefatto modello in run_dir", "run_dir": str(run)}

    create = _run(["ollama", "create", model_name, "-f", str(modelfile)], timeout=900.0)
    if not create.get("ok"):
        return {
            "ok": False,
            "error": "ollama create fallito",
            "details": create,
            "modelfile": str(modelfile),
        }

    meta = {
        "ok": True,
        "model_name": model_name,
        "modelfile": str(modelfile),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "ollama_stdout": create.get("stdout", "")[:500],
    }
    (run / "ollama_export.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Export Ollama: %s", model_name)
    return meta


async def promote_model(run_id: str, run_dir: str, eval_result: dict) -> dict:
    """Promuove modello se eval lo consiglia."""
    if not eval_result.get("promote_recommended"):
        return {
            "ok": False,
            "error": "Eval non raccomanda promote",
            "eval": eval_result,
        }
    export = await export_to_ollama(run_dir)
    if not export.get("ok"):
        return export

    # Aggiorna probe cache — forza re-probe
    from backend.core.ollama_model_router import probe_all_models

    await probe_all_models(force=True)
    return {
        "ok": True,
        "run_id": run_id,
        "model": export.get("model_name"),
        "eval": eval_result,
        "export": export,
    }
