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
LEGACY="/home/janis/JANICE"
if [ -f "$LEGACY/.env" ] || [ -f "$BRAIN/.env" ]; then
  touch "$BRAIN/.env"
  [ -f "$LEGACY/.env" ] && [ ! -s "$BRAIN/.env" ] && cp "$LEGACY/.env" "$BRAIN/.env"
  sed -i \
    -e "s|JANICE|JANIS|g" \
    -e "s|/home/janis/JANIS|$BRAIN|g" \
    -e "s|/home/janis/JANICE|$BRAIN|g" \
    -e "s|JANIS_PROJECT_DIR=.*|JANIS_PROJECT_DIR=$BRAIN|" \
    -e "s|JANIS_WORKSPACE=.*|JANIS_WORKSPACE=/home/janis|" \
    "$BRAIN/.env" 2>/dev/null || true
fi
python3.12 -m venv "$BRAIN/.venv" 2>/dev/null || python3 -m venv "$BRAIN/.venv"
"$BRAIN/.venv/bin/pip" install -q -U pip
"$BRAIN/.venv/bin/pip" install -q -r "$BRAIN/requirements.txt"
"$BRAIN/.venv/bin/python" -m py_compile \
  "$BRAIN/backend/routers/host_metrics.py" \
  "$BRAIN/backend/routers/scout.py" \
  "$BRAIN/backend/core/llm_router.py" \
  "$BRAIN/backend/routers/pocket_extended.py" \
  "$BRAIN/backend/routers/identity.py" \
  "$BRAIN/backend/routers/emergency.py" \
  "$BRAIN/backend/routers/kiosk.py"
REMOTE_VENV

echo "=== systemd + kiosk tty ==="
ssh "$REMOTE" "JANIS_HOME=/home/janis BRAIN_DIR='$BRAIN_DIR' bash '$REMOTE_ROOT/infra/kiosk/setup-janis-tty.sh'"

echo "=== sidecar + systemd user ==="
ssh "$REMOTE" "REMOTE_ROOT='$REMOTE_ROOT' BRAIN_DIR='$BRAIN_DIR' JANIS_HOME=/home/janis bash -s" <<'REMOTE_SIDECAR'
set -euo pipefail
ROOT="$REMOTE_ROOT"
BRAIN="$BRAIN_DIR"
bash "$ROOT/infra/sidecars/install-sidecars.sh"
bash "$ROOT/infra/sidecars/setup-systemd-user.sh"
REMOTE_SIDECAR

echo "=== linger (always-on user services) ==="
ssh "$REMOTE" 'sudo loginctl enable-linger janis 2>/dev/null && echo linger=OK || echo linger=SKIP'

echo "=== verifica finale ==="
ssh "$REMOTE" bash -s <<'EOF'
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
for s in janis-glances janis-litellm janis-qdrant janis; do
  printf "%-18s %s\n" "$s" "$(systemctl --user is-active "$s" 2>/dev/null)"
done
curl -sf http://127.0.0.1:8001/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('brain',d.get('service'),'llm',d.get('llm_provider',{}).get('active'))"
curl -sf http://127.0.0.1:8001/api/host/metrics | python3 -c "import sys,json;d=json.load(sys.stdin);print('glances',d.get('glances'),'disk',len(d.get('disk',[])))"
curl -sf http://127.0.0.1:6333/collections >/dev/null && echo qdrant OK || echo qdrant OFF
EOF

echo "=== Deploy completato ==="
