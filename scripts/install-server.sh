#!/usr/bin/env bash
# Installazione completa J.A.N.I.S. su server Linux 192.168.1.72
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${JANIS_SSH:-janis}"
REMOTE_ROOT="${JANIS_REMOTE_ROOT:-/home/janis/projects/J.A.N.I.S.}"
BRAIN_DIR="$REMOTE_ROOT/packages/brain"

echo "=== 1/6 rsync monorepo ==="
ssh "$REMOTE" "mkdir -p '$REMOTE_ROOT'"
rsync -az --delete \
  --exclude '.git' \
  --exclude 'packages/brain/.venv' \
  --exclude 'packages/brain/__pycache__' \
  --exclude '**/__pycache__' \
  --exclude 'apps/pocket/DerivedData' \
  "$ROOT/" "$REMOTE:$REMOTE_ROOT/"

echo "=== 2/6 sistema (sudo opzionale) ==="
ssh -tt "$REMOTE" bash -s <<'REMOTE_SYS' || echo "WARN: sudo saltato"
set +e
export DEBIAN_FRONTEND=noninteractive
sudo -n apt-get update -qq 2>/dev/null && sudo -n apt-get install -y -qq chromium-browser chromium xorg xinit x11-xserver-utils curl jq
sudo -n loginctl enable-linger janis 2>/dev/null
REMOTE_SYS

echo "=== 3/6 venv + .env + data ==="
ssh "$REMOTE" "BRAIN_DIR='$BRAIN_DIR' REMOTE_ROOT='$REMOTE_ROOT' bash -s" <<'REMOTE_BRAIN'
set -euo pipefail
BRAIN="$BRAIN_DIR"
LEGACY=/home/janis/JANICE

python3.12 -m venv "$BRAIN/.venv"
"$BRAIN/.venv/bin/pip" install -q -U pip wheel
"$BRAIN/.venv/bin/pip" install -q -r "$BRAIN/requirements.txt"

# .env Linux
if [ -f "$LEGACY/.env" ] && [ ! -f "$BRAIN/.env" ]; then
  cp "$LEGACY/.env" "$BRAIN/.env"
fi
if [ ! -f "$BRAIN/.env" ]; then
  cp "$BRAIN/.env.example" "$BRAIN/.env"
fi
sed -i \
  -e "s|JANICE|JANIS|g" \
  -e "s|/home/janis/JANIS|$BRAIN|g" \
  -e "s|/home/janis/JANICE|$BRAIN|g" \
  -e "s|JANIS_PROJECT_DIR=.*|JANIS_PROJECT_DIR=$BRAIN|" \
  -e "s|JANIS_WORKSPACE=.*|JANIS_WORKSPACE=/home/janis|" \
  -e "s|JANIS_MOVIES_PATH=.*|# JANIS_MOVIES_PATH=|" \
  "$BRAIN/.env"

mkdir -p "$BRAIN/data/memory" "$BRAIN/data/identity" "$BRAIN/data/pocket"
if [ -d "$LEGACY/data/memory" ]; then
  rsync -a "$LEGACY/data/memory/" "$BRAIN/data/memory/" 2>/dev/null || true
fi
if [ -d "$LEGACY/data/knowledge" ]; then
  rsync -a "$LEGACY/data/knowledge/" "$BRAIN/data/knowledge/" 2>/dev/null || true
fi

cd "$BRAIN"
"$BRAIN/.venv/bin/python" -c "import sys; sys.path.insert(0,'.'); from backend.main import app; print('import OK:', app.title)"
REMOTE_BRAIN

echo "=== 4/6 Ollama modelli ==="
ssh "$REMOTE" bash -s <<'REMOTE_OLLAMA'
set -euo pipefail
if ! systemctl is-active ollama >/dev/null 2>&1; then
  sudo systemctl enable --now ollama 2>/dev/null || true
fi
MODEL=$(grep '^OLLAMA_MODEL=' /home/janis/projects/J.A.N.I.S./packages/brain/.env 2>/dev/null | cut -d= -f2 || echo "gemma2:2b")
EMBED=$(grep '^OLLAMA_EMBED_MODEL=' /home/janis/projects/J.A.N.I.S./packages/brain/.env 2>/dev/null | cut -d= -f2 || echo "nomic-embed-text")
echo "Pull $MODEL ..."
ollama pull "$MODEL" || ollama pull gemma2:2b || true
echo "Pull $EMBED ..."
ollama pull "$EMBED" || true
ollama list
REMOTE_OLLAMA

echo "=== 5/6 systemd + kiosk tty ==="
ssh "$REMOTE" "JANIS_HOME=/home/janis BRAIN_DIR='$BRAIN_DIR' bash '$REMOTE_ROOT/infra/kiosk/setup-janis-tty.sh'"

echo "=== 6/6 avvio janis ==="
ssh "$REMOTE" bash -s <<'REMOTE_START'
set -euo pipefail
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
pkill -f '/home/janis/JANICE' 2>/dev/null || true
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user daemon-reload
systemctl --user enable janis
systemctl --user restart janis
sleep 3
echo "janis: $(systemctl --user is-active janis)"
curl -sf http://127.0.0.1:8001/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['service'], d['version'], 'ollama:', d['ollama']['online'])" 2>/dev/null
curl -sf -o /dev/null -w "server:%{http_code} " http://127.0.0.1:8001/server
curl -sf -o /dev/null -w "css:%{http_code} " http://127.0.0.1:8001/kiosk-static/server-infographic.css
curl -sf -o /dev/null -w "client:%{http_code}\n" http://127.0.0.1:8001/client
REMOTE_START

echo "=== INSTALLAZIONE COMPLETATA ==="
