#!/usr/bin/env bash
# Deploy J.A.N.I.S. brain + kiosk sul server Linux (janis@192.168.1.72)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${JANIS_SSH:-janis}"
REMOTE_ROOT="${JANIS_REMOTE_ROOT:-/home/janis/projects/J.A.N.I.S.}"
BRAIN_DIR="$REMOTE_ROOT/packages/brain"

echo "=== rsync monorepo → $REMOTE:$REMOTE_ROOT ==="
ssh "$REMOTE" "mkdir -p '$REMOTE_ROOT'"
rsync -az --delete \
  --exclude '.git' \
  --exclude 'packages/brain/.venv' \
  --exclude 'packages/brain/data/chat' \
  --exclude 'packages/brain/__pycache__' \
  --exclude '**/__pycache__' \
  --exclude 'apps/pocket/DerivedData' \
  "$ROOT/" "$REMOTE:$REMOTE_ROOT/"

echo "=== venv + dipendenze ==="
ssh "$REMOTE" "BRAIN_DIR='$BRAIN_DIR' bash -s" <<'REMOTE_VENV'
set -euo pipefail
BRAIN="$BRAIN_DIR"
if [ -f /home/janis/JANICE/.env ] && [ ! -f "$BRAIN/.env" ]; then
  cp /home/janis/JANICE/.env "$BRAIN/.env"
  sed -i "s|JANICE|JANIS|g; s|/home/janis/JANICE|$BRAIN|g" "$BRAIN/.env" || true
fi
python3.12 -m venv "$BRAIN/.venv" 2>/dev/null || python3 -m venv "$BRAIN/.venv"
"$BRAIN/.venv/bin/pip" install -q -U pip
"$BRAIN/.venv/bin/pip" install -q -r "$BRAIN/requirements.txt"
"$BRAIN/.venv/bin/python" -m py_compile \
  "$BRAIN/backend/routers/pocket_extended.py" \
  "$BRAIN/backend/routers/identity.py" \
  "$BRAIN/backend/routers/emergency.py" \
  "$BRAIN/backend/routers/kiosk.py"
REMOTE_VENV

echo "=== systemd + kiosk tty ==="
ssh "$REMOTE" "JANIS_HOME=/home/janis BRAIN_DIR='$BRAIN_DIR' bash '$REMOTE_ROOT/infra/kiosk/setup-janis-tty.sh'"

echo "=== stop JANICE legacy, avvia janis ==="
ssh "$REMOTE" bash -s <<'EOF'
set -euo pipefail
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
sleep 1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user daemon-reload
systemctl --user enable janis
systemctl --user restart janis
sleep 2
systemctl --user is-active janis
curl -sf http://127.0.0.1:8001/api/status | head -c 200
echo
curl -sf -o /dev/null -w '/server → %{http_code}\n' http://127.0.0.1:8001/server
EOF

echo "=== Deploy completato ==="
