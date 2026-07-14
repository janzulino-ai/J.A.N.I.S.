#!/usr/bin/env bash
# JANIS Fleet bridge — Mac Mini → brain Windows/WSL (Mode A)
set -euo pipefail

JANIS_ROOT="${JANIS_ROOT:-$HOME/projects/J.A.N.I.S.}"
HUB_LAN_IP="${JANIS_HUB_LAN_IP:-192.168.1.73}"
FLEET_NODE_ID="${FLEET_NODE_ID:-mac-node}"
FLEET_HUB_URL="${FLEET_HUB_URL:-ws://${HUB_LAN_IP}:8001/ws/fleet-node}"
LABEL="ai.janzulino.janis.fleet-bridge"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/janis"
BRIDGE_SH="$JANIS_ROOT/packages/brain/bridge/client.py"
LEGACY_BRIDGE="$HOME/JANICE/bridge/client.py"

mkdir -p "$LOG_DIR"

if [ -f "$BRIDGE_SH" ]; then
  BRIDGE_CMD="$BRIDGE_SH"
  PYTHON="${JANIS_PYTHON:-python3}"
elif [ -f "$LEGACY_BRIDGE" ]; then
  echo "WARN: uso bridge legacy $LEGACY_BRIDGE — preferisci monorepo $BRIDGE_SH"
  BRIDGE_CMD="$LEGACY_BRIDGE"
  PYTHON="${JANIS_PYTHON:-python3}"
else
  echo "ERRORE: bridge non trovato."
  echo "  Monorepo: $BRIDGE_SH"
  echo "  Legacy:   $LEGACY_BRIDGE"
  echo "Clone JANIS in ~/projects/J.A.N.I.S. o imposta JANIS_ROOT."
  exit 1
fi

# websockets per bridge client
if ! "$PYTHON" -c "import websockets" 2>/dev/null; then
  echo "Installazione websockets..."
  "$PYTHON" -m pip install --user websockets
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${BRIDGE_CMD}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>FLEET_HUB_URL</key>
    <string>${FLEET_HUB_URL}</string>
    <key>FLEET_NODE_ID</key>
    <string>${FLEET_NODE_ID}</string>
    <key>MAC_BRIDGE_TOKEN</key>
    <string>${MAC_BRIDGE_TOKEN:-}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/fleet-bridge.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/fleet-bridge.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "Fleet bridge installato."
echo "  Hub:       ${FLEET_HUB_URL}"
echo "  node_id:   ${FLEET_NODE_ID}"
echo "  Log:       ${LOG_DIR}/fleet-bridge.log"
echo "  Verifica:  curl http://${HUB_LAN_IP}:8001/api/fleet/nodes"
