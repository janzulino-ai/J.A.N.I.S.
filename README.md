# J.A.N.I.S. monorepo

**J**ust **A**nother **N**euralgic **I**mproving **S**erver

**Repo ufficiale** (unica sorgente locale + GitHub):  
https://github.com/janzulino-ai/J.A.N.I.S.  
Cartella locale: `~/Documents/J.A.N.I.S./`

Vedi [docs/OFFICIAL-REPO.md](docs/OFFICIAL-REPO.md)

| Path | Ruolo |
|------|--------|
| `packages/brain/` | Hub FastAPI su **server Linux** |
| `packages/kiosk/` | HUD HDMI `/server` |
| `packages/client-web/` | Client 3 colonne |
| `packages/orchestrator/` | Doc orchestrazione + evolve |
| `infra/win-vm/` | KVM Windows VM |
| `workspaces/` | Auto-evoluzione JANIS |
| `apps/pocket/` | iOS corpo sensoriale |

## Avvio (server Linux)

```bash
cd packages/brain
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Kiosk

```bash
bash infra/kiosk/setup-janis-tty.sh
systemctl --user enable --now janis
```

## Sync

```bash
bash scripts/push-all.sh "messaggio commit"
```
