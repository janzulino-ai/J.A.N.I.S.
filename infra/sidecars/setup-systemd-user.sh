#!/usr/bin/env bash
# Installa unit systemd user per brain + sidecar
set -euo pipefail
JANIS_HOME="${JANIS_HOME:-$HOME}"
ROOT="${JANIS_ROOT:-$JANIS_HOME/projects/J.A.N.I.S.}"
BRAIN="${JANIS_BRAIN:-$ROOT/packages/brain}"
UNIT_DIR="$JANIS_HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR" "$JANIS_HOME/logs/sidecars"

chmod +x "$ROOT/infra/sidecars/"*.sh "$ROOT/infra/glances/"*.sh \
  "$ROOT/infra/litellm/"*.sh "$ROOT/infra/qdrant/"*.sh 2>/dev/null || true

# Env sidecar nel .env brain
touch "$BRAIN/.env"
for kv in \
  "GLANCES_URL=http://127.0.0.1:61208" \
  "LITELLM_PROXY_URL=http://127.0.0.1:4000/v1" \
  "QDRANT_URL=http://127.0.0.1:6333"; do
  key="${kv%%=*}"
  grep -q "^${key}=" "$BRAIN/.env" || echo "$kv" >> "$BRAIN/.env"
done

cat > "$UNIT_DIR/janis-glances.service" <<EOF
[Unit]
Description=JANIS Glances monitor
After=network-online.target

[Service]
Type=simple
Environment=JANIS_BRAIN=$BRAIN
ExecStart=$ROOT/infra/glances/start-glances.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/janis-litellm.service" <<EOF
[Unit]
Description=JANIS LiteLLM proxy
After=network-online.target janis-glances.service

[Service]
Type=simple
Environment=JANIS_BRAIN=$BRAIN
ExecStart=$ROOT/infra/litellm/start-litellm.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/janis-qdrant.service" <<EOF
[Unit]
Description=JANIS Qdrant vector store
After=network-online.target

[Service]
Type=simple
Environment=QDRANT_INSTALL=$JANIS_HOME/.local/qdrant
Environment=QDRANT_STORAGE=$JANIS_HOME/.local/share/janis-qdrant
ExecStartPre=$ROOT/infra/qdrant/install-qdrant.sh
ExecStart=$ROOT/infra/qdrant/run-qdrant-foreground.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/janis.service" <<EOF
[Unit]
Description=J.A.N.I.S. brain
After=network-online.target janis-glances.service janis-litellm.service janis-qdrant.service
Wants=janis-glances.service janis-litellm.service janis-qdrant.service

[Service]
Type=simple
WorkingDirectory=$BRAIN
Environment=JANIS_PROJECT_DIR=$BRAIN
Environment=HOME=$JANIS_HOME
ExecStart=$BRAIN/.venv/bin/python run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Rimuovi crontab @reboot duplicato (conflitto porta 8001)
crontab -l 2>/dev/null | grep -v '# JANIS' | crontab - 2>/dev/null || crontab -r 2>/dev/null || true
pkill -f 'packages/brain/.venv/bin/python run.py' 2>/dev/null || true
sleep 2

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user daemon-reload
systemctl --user enable janis-glances janis-litellm janis-qdrant janis
systemctl --user restart janis-glances janis-litellm janis-qdrant
sleep 3
systemctl --user restart janis
sleep 3

echo "=== Servizi ==="
for s in janis-glances janis-litellm janis-qdrant janis; do
  printf "%-18s %s\n" "$s" "$(systemctl --user is-active "$s" 2>/dev/null || echo failed)"
done

curl -sf "http://127.0.0.1:61208/api/4/cpu" >/dev/null 2>&1 && echo "Glances API OK" || echo "Glances API OFF"
curl -sf "http://127.0.0.1:4000/health/liveliness" >/dev/null 2>&1 || curl -sf "http://127.0.0.1:4000/" >/dev/null 2>&1 && echo "LiteLLM OK" || echo "LiteLLM OFF"
curl -sf "http://127.0.0.1:6333/collections" >/dev/null 2>&1 && echo "Qdrant OK" || echo "Qdrant OFF"
curl -sf "http://127.0.0.1:8001/api/status" >/dev/null 2>&1 && echo "JANIS brain OK" || echo "JANIS brain OFF"
