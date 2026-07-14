#!/usr/bin/env bash
# Installa dipendenze sidecar nel venv brain (no Docker obbligatorio)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAIN="${JANIS_BRAIN:-$ROOT/packages/brain}"
VENV="$BRAIN/.venv/bin/pip"

if [ ! -x "$VENV" ]; then
  echo "venv brain mancante: $BRAIN/.venv — esegui deploy-server.sh prima"
  exit 1
fi

echo "=== pip sidecar deps ==="
"$VENV" install -q -U 'glances[web]' 'litellm[proxy]' PyYAML 2>/dev/null || \
  "$VENV" install -q -U glances litellm PyYAML

echo "OK: glances + litellm nel venv brain"
