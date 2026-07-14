#!/usr/bin/env bash
# LiteLLM proxy — usa venv brain
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAIN="${JANIS_BRAIN:-$ROOT/packages/brain}"
CONFIG="${ROOT}/infra/litellm/config.yaml"
BIN="$BRAIN/.venv/bin/litellm"

if [ ! -x "$BIN" ]; then
  echo "LiteLLM non installato. Esegui: infra/sidecars/install-sidecars.sh"
  exit 1
fi

# Carica .env brain se presente
if [ -f "$BRAIN/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^(OPENROUTER_API_KEY|LITELLM_MASTER_KEY|API_DAILY_BUDGET_USD)=' "$BRAIN/.env" | sed 's/\r$//')
  set +a
fi

export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-janis-local}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

exec "$BIN" --config "$CONFIG" --port 4000 --host 127.0.0.1
