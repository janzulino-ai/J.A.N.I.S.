"""Wrapper training Unsloth — subprocess venv isolato."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.core.llm_lab.curate import curate_dataset
from backend.core.llm_lab.eval import evaluate_model
from backend.core.llm_lab.export import export_to_ollama, promote_model
from backend.core.llm_lab.gpu import gpu_status, unsloth_venv_ready
from backend.core.llm_lab.harvest import harvest_chats
from backend.core.llm_lab.jobs import active_run, create_run, update_run
from backend.core.llm_lab.paths import (
    curated_dataset_path,
    lab_configs_dir,
    lab_train_script,
    lab_venv_python,
)

logger = logging.getLogger("JANIS.Lab.Train")

_running_task: asyncio.Task | None = None


def _default_config() -> dict:
    return {
        "base_model": settings.LAB_BASE_MODEL,
        "max_steps": settings.LAB_MAX_STEPS,
        "lora_r": settings.LAB_LORA_R,
        "learning_rate": settings.LAB_LEARNING_RATE,
        "batch_size": settings.LAB_BATCH_SIZE,
    }


def _write_run_config(run_dir: Path, cfg: dict) -> Path:
    path = run_dir / "train_config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def _run_subprocess(cmd: list[str], log_path: Path, timeout: float = 7200.0) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as logf:
        logf.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
        logf.write(" ".join(cmd) + "\n")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            lines: list[str] = []
            async for chunk in proc.stdout:
                line = chunk.decode(errors="replace")
                lines.append(line)
                logf.write(line)
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            out = "".join(lines)
            return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "output": out[-3000:]}
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": "training timeout"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}


async def _pipeline(run_id: str) -> None:
    job = update_run(run_id, status="running", stage="preflight")
    run_dir = Path((job or {}).get("run_dir", ""))
    log_path = Path((job or {}).get("log_path", run_dir / "train.log"))

    try:
        # Curate fresh
        update_run(run_id, stage="curate")
        cur = await curate_dataset()
        dataset = curated_dataset_path()
        if cur.get("total", 0) < settings.LAB_MIN_DATASET_SIZE:
            update_run(
                run_id,
                status="failed",
                stage="curate",
                error=f"Dataset insufficiente: {cur.get('total')} < {settings.LAB_MIN_DATASET_SIZE}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return

        gpu = gpu_status()
        venv_py = lab_venv_python()
        venv_chk = unsloth_venv_ready(venv_py)
        if not gpu.get("available"):
            update_run(
                run_id,
                status="failed",
                stage="preflight",
                error=f"GPU non disponibile: {gpu.get('reason', 'unknown')}",
                metrics={"gpu": gpu, "curate": cur},
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return
        if not venv_chk.get("ready"):
            update_run(
                run_id,
                status="failed",
                stage="preflight",
                error=f"Unsloth venv non pronto: {venv_chk.get('reason') or venv_chk.get('stderr')}",
                metrics={"gpu": gpu, "venv": venv_chk, "hint": "bash infra/lab/setup-unsloth.sh"},
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return

        cfg = (job or {}).get("config") or _default_config()
        _write_run_config(run_dir, cfg)
        script = lab_train_script()
        if not script.exists():
            update_run(
                run_id,
                status="failed",
                error=f"Script training assente: {script}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return

        update_run(run_id, stage="train", metrics={"gpu": gpu, "curate": cur})
        cmd = [
            str(venv_py),
            str(script),
            "--dataset", str(dataset),
            "--output", str(run_dir),
            "--base-model", cfg.get("base_model", settings.LAB_BASE_MODEL),
            "--max-steps", str(cfg.get("max_steps", settings.LAB_MAX_STEPS)),
            "--lora-r", str(cfg.get("lora_r", settings.LAB_LORA_R)),
            "--learning-rate", str(cfg.get("learning_rate", settings.LAB_LEARNING_RATE)),
            "--batch-size", str(cfg.get("batch_size", settings.LAB_BATCH_SIZE)),
            "--ollama-name", settings.LAB_OLLAMA_MODEL_NAME,
        ]
        train_result = await _run_subprocess(cmd, log_path)
        train_meta_path = run_dir / "train_result.json"
        train_meta = {}
        if train_meta_path.exists():
            try:
                train_meta = json.loads(train_meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        if not train_result.get("ok") or not train_meta.get("ok"):
            update_run(
                run_id,
                status="failed",
                stage="train",
                error=train_meta.get("error") or train_result.get("error") or "training fallito",
                metrics={"train": train_meta or train_result},
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return

        model_tag = settings.LAB_OLLAMA_MODEL_NAME
        update_run(run_id, stage="eval")
        eval_result = await evaluate_model(model_tag if train_meta.get("ollama_imported") else settings.LAB_EVAL_BASELINE)
        # Se training ha già importato in ollama, eval sul custom
        if train_meta.get("ollama_model"):
            eval_result = await evaluate_model(train_meta["ollama_model"])

        update_run(run_id, stage="export", metrics={"train": train_meta, "eval": eval_result})

        export_result = {}
        if train_meta.get("ollama_model"):
            export_result = {"ok": True, "model_name": train_meta["ollama_model"], "via": "train_script"}
        else:
            export_result = await export_to_ollama(str(run_dir))

        promote_result = None
        if settings.LAB_AUTO_PROMOTE and eval_result.get("promote_recommended"):
            promote_result = await promote_model(run_id, str(run_dir), eval_result)

        update_run(
            run_id,
            status="completed",
            stage="done",
            metrics={
                "train": train_meta,
                "eval": eval_result,
                "export": export_result,
                "promote": promote_result,
            },
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Lab run %s completato", run_id)
    except Exception as e:
        logger.exception("Lab pipeline %s", run_id)
        update_run(
            run_id,
            status="failed",
            error=str(e)[:300],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


async def start_training(*, config: dict | None = None, force: bool = False) -> dict:
    """Avvia job training async se non già in corso."""
    global _running_task
    if not settings.LAB_ENABLED:
        return {"ok": False, "error": "LAB_ENABLED=false"}

    if active_run() and not force:
        ar = active_run()
        return {"ok": False, "error": "Job già in corso", "run_id": ar.get("id") if ar else None}

    if _running_task and not _running_task.done():
        return {"ok": False, "error": "Pipeline già avviata"}

    dataset = str(curated_dataset_path())
    cfg = {**_default_config(), **(config or {})}
    job = create_run(dataset=dataset, base_model=cfg["base_model"], config=cfg)
    run_id = job["id"]
    _running_task = asyncio.create_task(_pipeline(run_id), name=f"lab-train-{run_id}")
    return {"ok": True, "run_id": run_id, "status": "started"}


async def run_full_cycle(*, harvest_first: bool = True) -> dict:
    """Harvest → curate → train (se soglia raggiunta)."""
    steps: list[dict] = []
    if harvest_first:
        h = await harvest_chats()
        steps.append({"step": "harvest", **h})
    c = await curate_dataset()
    steps.append({"step": "curate", **c})

    total = c.get("total", 0)
    if total < settings.LAB_MIN_DATASET_SIZE:
        return {
            "ok": True,
            "action": "skipped_train",
            "reason": f"dataset {total} < {settings.LAB_MIN_DATASET_SIZE}",
            "steps": steps,
        }

    if not settings.LAB_AUTO_TRAIN_ENABLED:
        return {
            "ok": True,
            "action": "ready_for_train",
            "steps": steps,
            "hint": "POST /api/lab/train per avviare",
        }

    gpu = gpu_status()
    if not gpu.get("available") or not gpu.get("idle", False):
        return {
            "ok": True,
            "action": "deferred_train",
            "reason": "GPU occupata o assente",
            "steps": steps,
            "gpu": gpu,
        }

    t = await start_training()
    steps.append({"step": "train", **t})
    return {"ok": True, "action": "train_started", "steps": steps}
