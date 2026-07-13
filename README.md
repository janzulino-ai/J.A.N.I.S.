# J.A.N.I.S. monorepo

**J**ust **A**nother **N**euralgic **I**mproving **S**erver

| Path | Ruolo |
|------|--------|
| `packages/brain/` | Hub FastAPI su **server Linux** |
| `packages/kiosk/` | HUD HDMI `/server` |
| `packages/client-web/` | Client 3 colonne |
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
