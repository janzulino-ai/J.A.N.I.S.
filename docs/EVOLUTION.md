# Auto-evoluzione monorepo

## Percorsi

- **Monorepo**: `J.A.N.I.S./`
- **Brain**: `packages/brain/`
- **Scrivibile da JANIS**: `workspaces/`

## API

| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/evolve/paths` | Radici monorepo + workspace |
| `GET /api/evolve/files` | Elenco file sotto workspaces |
| `POST /api/evolve/write` | Scrittura sicura (`path` relativo) |
| `GET /api/gaps` | Gap capacità aperti |

## Flusso

1. JANIS rileva gap → `capability_gaps` o chat
2. Propone in `workspaces/evolve/proposals/`
3. `reflect` / `autodev` / utente promuove in `packages/`
4. `scripts/push-all.sh` → GitHub → `deploy-server.sh`

## Config

```env
JANIS_MONOREPO_ROOT=/home/janis/projects/J.A.N.I.S.
```
