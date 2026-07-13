# Repo ufficiale — J.A.N.I.S.

| Dove | Path |
|------|------|
| **GitHub** | https://github.com/janzulino-ai/J.A.N.I.S. |
| **Mac locale** | `~/Documents/J.A.N.I.S./` |
| **Server Linux** | `~/projects/J.A.N.I.S./` |

## Struttura

```
J.A.N.I.S./
├── packages/brain/     # FastAPI brain
├── packages/kiosk/     # HUD /server
├── packages/client-web/
├── apps/pocket/        # iOS
├── infra/
├── docs/
└── scripts/
```

## Non usare più

- `Documents/JANICE` → archivio; brain in `packages/brain/`
- `Documents/JANICE-Pocket` → archivio; pocket in `apps/pocket/`
- GitHub `JANICE` / `JANICE-Pocket` → solo storico fino a merge completo
- Server `~/JANICE` → sostituito da `~/projects/J.A.N.I.S./`

## Sync

```bash
cd ~/Documents/J.A.N.I.S.
bash scripts/push-all.sh "messaggio"
bash scripts/deploy-server.sh   # → 192.168.1.72
```
