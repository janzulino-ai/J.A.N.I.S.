# orchestrator

Stato orchestrazione e cost routing — implementazione in `packages/brain/backend/core/`:

- `cost_router.py` — budget API cloud
- `orchestrator.py` / scheduler — loop autonomia
- `capability_gaps.py` — registro gap

Cartelle runtime: `workspaces/evolve/`, API `/api/evolve/*`, `/api/gaps/*`.

JANIS usa questi moduli per auto-miglioramento; nuova logica LangGraph-like va qui o in `packages/brain/backend/core/`.
