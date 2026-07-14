#!/usr/bin/env bash
# Avvio brain JANIS in WSL (local-only)
set -euo pipefail
export PATH="$HOME/.local/bin:${PATH:-}"
JANIS="${JANIS:-$HOME/projects/J.A.N.I.S.}"
BRAIN="$JANIS/packages/brain"
VENV="${JANIS_VENV:-$HOME/janis-venv}"
[ -f "$HOME/.janis-wsl.env" ] && source "$HOME/.janis-wsl.env"

if [ ! -x "$VENV/bin/python" ]; then
  echo "venv mancante — esegui: bash $JANIS/infra/wsl/finish-setup.sh"
  exit 1
fi

cd "$BRAIN"
OLLAMA_BASE_URL="$(grep -m1 '^OLLAMA_BASE_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r')"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
if ! curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
  if command -v ollama >/dev/null; then
    echo "Avvio ollama serve..."
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 3
  else
    echo "WARN: Ollama non raggiungibile — avvia Ollama Windows (OLLAMA_HOST=0.0.0.0:11434)"
  fi
fi

cd "$BRAIN"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8001}"
exec "$VENV/bin/python" run.py
