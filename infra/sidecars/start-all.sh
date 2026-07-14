#!/usr/bin/env bash
# Avvia sidecar JANIS (Glances + LiteLLM opzionale + Qdrant se Docker)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAIN="${JANIS_BRAIN:-$ROOT/packages/brain}"
LOGDIR="${JANIS_SIDECAR_LOG:-/home/janis/logs/sidecars}"
mkdir -p "$LOGDIR"

# Install deps se mancanti
if [ ! -x "$BRAIN/.venv/bin/glances" ] || [ ! -x "$BRAIN/.venv/bin/litellm" ]; then
  bash "$ROOT/infra/sidecars/install-sidecars.sh"
fi

_start_bg() {
  local name="$1"
  shift
  if pgrep -f "sidecar-$name" >/dev/null 2>&1 || pgrep -f "$name.*61208" >/dev/null 2>&1; then
    echo "[$name] già in esecuzione"
    return 0
  fi
  echo "[$name] avvio..."
  nohup env SIDECAR_NAME="$name" "$@" >>"$LOGDIR/$name.log" 2>&1 &
  sleep 2
  if pgrep -f "$name" >/dev/null 2>&1 || [ "$name" = "qdrant" ]; then
    echo "[$name] OK — log: $LOGDIR/$name.log"
  else
    echo "[$name] FALLITO — vedi $LOGDIR/$name.log"
    tail -5 "$LOGDIR/$name.log" 2>/dev/null || true
    return 1
  fi
}

# Glances (sempre consigliato)
_start_bg glances bash "$ROOT/infra/glances/start-glances.sh" || true

# LiteLLM solo se .env ha proxy o LITELLM abilitato
if grep -qE '^LITELLM_PROXY_URL=' "$BRAIN/.env" 2>/dev/null; then
  _start_bg litellm bash "$ROOT/infra/litellm/start-litellm.sh" || true
else
  echo "[litellm] SKIP — imposta LITELLM_PROXY_URL=http://127.0.0.1:4000/v1 in .env per abilitare"
fi

# Qdrant opzionale
bash "$ROOT/infra/qdrant/start-qdrant.sh" | tee -a "$LOGDIR/qdrant.log" || true

echo "=== Sidecar status ==="
curl -sf "http://127.0.0.1:61208/api/4/cpu" >/dev/null 2>&1 || curl -sf "http://127.0.0.1:61208/api/3/cpu" >/dev/null 2>&1 && echo "Glances :61208 OK" || echo "Glances :61208 OFF"
curl -sf "http://127.0.0.1:4000/health" >/dev/null 2>&1 && echo "LiteLLM :4000 OK" || echo "LiteLLM :4000 OFF"
curl -sf "http://127.0.0.1:6333/collections" >/dev/null 2>&1 && echo "Qdrant :6333 OK" || echo "Qdrant :6333 OFF (docker assente o non avviato)"
