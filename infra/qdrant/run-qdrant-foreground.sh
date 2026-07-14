#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${QDRANT_INSTALL:-$HOME/.local/qdrant}"
STORAGE="${QDRANT_STORAGE:-$HOME/.local/share/janis-qdrant}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${QDRANT_PORT:-6333}"
[ -x "$INSTALL_DIR/qdrant" ] || bash "$ROOT/install-qdrant.sh"
mkdir -p "$STORAGE"
cd "$STORAGE"
# Config con path assoluto storage
cfg=$(mktemp)
sed "s|./storage|$STORAGE|g" "$ROOT/config.yaml" > "$cfg"
exec "$INSTALL_DIR/qdrant" --config-path "$cfg"
