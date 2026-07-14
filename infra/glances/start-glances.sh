#!/usr/bin/env bash
# Glances API REST — usa venv brain
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAIN="${JANIS_BRAIN:-$ROOT/packages/brain}"
BIN="$BRAIN/.venv/bin/glances"

if [ ! -x "$BIN" ]; then
  echo "Glances non installato. Esegui: infra/sidecars/install-sidecars.sh"
  exit 1
fi

PORT="${GLANCES_PORT:-61208}"
exec "$BIN" -w --port "$PORT" --bind 127.0.0.1
