"""Tool ReAct laboratorio LLM — harvest, train, status, promote."""
from __future__ import annotations

from backend.core.tools.registry import register


@register("lab")
async def lab_tool(args: dict) -> str:
    action = (args.get("action") or "status").lower().strip()
    run_id = (args.get("run_id") or args.get("id") or "").strip()

    if action == "status":
        from backend.core.llm_lab.status import lab_status

        s = await lab_status()
        gpu = s.get("gpu") or {}
        lines = [
            f"LLM Lab: enabled={s.get('enabled')} curated={s.get('curated_examples')} "
            f"ready_train={s.get('ready_train')}",
            f"GPU: {gpu.get('count', 0)} device(s) available={gpu.get('available')}",
            f"Base: {s.get('base_model')} → Ollama: {s.get('ollama_model_name')}",
        ]
        if s.get("active_run"):
            ar = s["active_run"]
            lines.append(f"Run attivo: {ar.get('id')} stage={ar.get('stage')}")
        if s.get("setup_hint"):
            lines.append(f"Setup: {s['setup_hint']}")
        return "\n".join(lines)

    if action == "harvest":
        from backend.core.llm_lab.harvest import harvest_chats

        r = await harvest_chats(force_all=bool(args.get("force_all")))
        return f"Harvest: {r.get('examples', 0)} esempi da {r.get('files_processed', 0)} file"

    if action == "curate":
        from backend.core.llm_lab.curate import curate_dataset

        r = await curate_dataset()
        return f"Curate: {r.get('total', 0)} totali (+{r.get('added', 0)} nuovi)"

    if action == "train":
        from backend.core.llm_lab.train import start_training

        cfg = {}
        for k in ("base_model", "max_steps", "lora_r", "learning_rate", "batch_size"):
            if args.get(k) is not None:
                cfg[k] = args[k]
        r = await start_training(config=cfg or None, force=bool(args.get("force")))
        if not r.get("ok"):
            return f"Train non avviato: {r.get('error')}"
        return f"Training avviato run_id={r.get('run_id')}"

    if action == "cycle":
        from backend.core.llm_lab.train import run_full_cycle

        r = await run_full_cycle(harvest_first=bool(args.get("harvest_first", True)))
        return f"Cycle: action={r.get('action')} steps={len(r.get('steps') or [])}"

    if action == "runs":
        from backend.core.llm_lab.jobs import list_runs

        runs = list_runs(limit=int(args.get("limit") or 5))
        lines = [f"LLM Lab runs: {len(runs)}"]
        for run in runs:
            lines.append(f"- [{run.get('status')}] {run.get('id')} stage={run.get('stage')}")
        return "\n".join(lines)

    if action == "promote":
        if not run_id:
            return "run_id obbligatorio per lab promote"
        from backend.core.llm_lab.eval import evaluate_model
        from backend.core.llm_lab.export import promote_model
        from backend.core.llm_lab.jobs import get_run

        run = get_run(run_id)
        if not run:
            return f"Run {run_id} non trovato"
        metrics = run.get("metrics") or {}
        eval_result = metrics.get("eval")
        if not eval_result:
            from backend.config import settings

            eval_result = await evaluate_model(settings.LAB_OLLAMA_MODEL_NAME)
        r = await promote_model(run_id, run.get("run_dir", ""), eval_result)
        if not r.get("ok"):
            return f"Promote fallito: {r.get('error')}"
        return f"Promosso modello {r.get('model')}"

    return (
        f"Azione lab sconosciuta: {action}. "
        "Usa: status|harvest|curate|train|cycle|runs|promote"
    )
