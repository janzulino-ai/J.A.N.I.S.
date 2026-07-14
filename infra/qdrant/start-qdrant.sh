#!/usr/bin/env bash
# Avvia Qdrant: Docker → binario nativo → skip
set -euo pipefail
NAME=janis-qdrant
PORT="${QDRANT_PORT:-6333}"
INSTALL_DIR="${QDRANT_INSTALL:-$HOME/.local/qdrant}"
STORAGE="${QDRANT_STORAGE:-$HOME/.local/share/janis-qdrant}"

if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
    docker start "$NAME" 2>/dev/null || true
  else
    docker run -d --name "$NAME" -p "${PORT}:6333" -v janis-qdrant-data:/qdrant/storage qdrant/qdrant:latest
  fi
  echo "Qdrant (docker): http://127.0.0.1:$PORT"
  exit 0
fi

if [ ! -x "$INSTALL_DIR/qdrant" ]; then
  bash "$(dirname "$0")/install-qdrant.sh" || {
    echo "SKIP: Qdrant non installato"
    exit 0
  }
fi

mkdir -p "$STORAGE"
if pgrep -f "$INSTALL_DIR/qdrant" >/dev/null 2>&1; then
  echo "Qdrant nativo già in esecuzione"
  exit 0
fi

nohup "$INSTALL_DIR/qdrant" --storage-path "$STORAGE" --http-port "$PORT" >>"${JANIS_SIDECAR_LOG:-$HOME/logs/sidecars}/qdrant.log" 2>&1 &
sleep 2
curl -sf "http://127.0.0.1:$PORT/collections" >/dev/null && echo "Qdrant (native): http://127.0.0.1:$PORT" || echo "Qdrant avvio in corso..."
