"""API laboratorio LLM — harvest, curate, train, status, promote."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


class LabTrainBody(BaseModel):
    base_model: str | None = None
    max_steps: int | None = None
    lora_r: int | None = None
    learning_rate: float | None = None
    batch_size: int | None = None
    force: bool = False


class LabAuditBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    teacher_response: str = Field(..., min_length=1)
    student_response: str = Field(..., min_length=1)
    student_model: str | None = None
    teacher_model: str | None = None
    run_id: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.get("/api/lab/status")
async def api_lab_status():
    from backend.core.llm_lab.status import lab_status

    return await lab_status()


@router.get("/api/lab/runs")
async def api_lab_runs(limit: int = Query(default=20, ge=1, le=100)):
    from backend.core.llm_lab.jobs import list_runs

    return {"runs": list_runs(limit=limit)}


@router.get("/api/lab/runs/{run_id}")
async def api_lab_run(run_id: str):
    from backend.core.llm_lab.jobs import get_run

    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run non trovato")
    return run


@router.post("/api/lab/harvest")
async def api_lab_harvest(force_all: bool = Query(default=False)):
    from backend.core.llm_lab.harvest import harvest_chats

    return await harvest_chats(force_all=force_all)


@router.post("/api/lab/curate")
async def api_lab_curate():
    from backend.core.llm_lab.curate import curate_dataset

    return await curate_dataset()


@router.post("/api/lab/train")
async def api_lab_train(body: LabTrainBody | None = None):
    from backend.core.llm_lab.train import start_training

    cfg = {}
    if body:
        for k in ("base_model", "max_steps", "lora_r", "learning_rate", "batch_size"):
            v = getattr(body, k, None)
            if v is not None:
                cfg[k] = v
        result = await start_training(config=cfg or None, force=body.force)
    else:
        result = await start_training()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error") or "train non avviato")
    return result


@router.post("/api/lab/cycle")
async def api_lab_cycle(harvest_first: bool = Query(default=True)):
    from backend.core.llm_lab.train import run_full_cycle

    return await run_full_cycle(harvest_first=harvest_first)


@router.post("/api/lab/promote/{run_id}")
async def api_lab_promote(run_id: str):
    from backend.core.llm_lab.eval import evaluate_model
    from backend.core.llm_lab.export import promote_model
    from backend.core.llm_lab.jobs import get_run

    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run non trovato")
    if run.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Run non completato")

    metrics = run.get("metrics") or {}
    eval_result = metrics.get("eval")
    if not eval_result:
        from backend.config import settings

        model = settings.LAB_OLLAMA_MODEL_NAME
        eval_result = await evaluate_model(model)

    result = await promote_model(run_id, run.get("run_dir", ""), eval_result)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "promote fallito")
    return result


@router.post("/api/lab/eval")
async def api_lab_eval(model: str = Query(..., min_length=1)):
    from backend.core.llm_lab.eval import evaluate_model

    return await evaluate_model(model)


@router.get("/api/lab/audits")
async def api_lab_audits(limit: int = Query(default=20, ge=1, le=100)):
    from backend.core.llm_lab.audit import list_audits

    return {"audits": list_audits(limit=limit)}


@router.get("/api/lab/audits/{audit_id}")
async def api_lab_audit(audit_id: str):
    from backend.core.llm_lab.audit import load_audit

    audit = load_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trovato")
    return audit


@router.post("/api/lab/audit")
async def api_lab_audit_run(body: LabAuditBody):
    from backend.core.llm_lab.audit import audit_responses

    result = await audit_responses(
        prompt=body.prompt,
        teacher_response=body.teacher_response,
        student_response=body.student_response,
        student_model=body.student_model,
        teacher_model=body.teacher_model,
        run_id=body.run_id,
        tags=body.tags,
    )
    if not result.get("ok") and result.get("error") and not result.get("audit"):
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result
