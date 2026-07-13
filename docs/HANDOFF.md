# HANDOFF — J.A.N.I.S.

## Repo ufficiale

Solo **J.A.N.I.S.** — `~/Documents/J.A.N.I.S./` (Mac), `~/projects/J.A.N.I.S./` (server), GitHub `janzulino-ai/J.A.N.I.S.`

## Architettura (aggiornata)

- **Brain**: server **Linux** `192.168.1.72` — non Windows
- **Windows**: solo **VM win-vm** sulla stessa macchina (HDMI RTX)
- **Kiosk**: tty1 → Chromium → `http://127.0.0.1:8001/server`

## Perso luglio 2026

HUD hud17 sul vecchio `~/projects/JANIS` — ricostruito in `packages/kiosk/`.

## Deploy server

```bash
# Da Mac (rsync + systemd)
bash scripts/deploy-server.sh

# Oppure manuale sul server:
git clone https://github.com/janzulino-ai/J.A.N.I.S..git ~/projects/J.A.N.I.S.
cd ~/projects/J.A.N.I.S./packages/brain
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
bash ../../infra/kiosk/setup-janis-tty.sh
systemctl --user enable --now janis
```
