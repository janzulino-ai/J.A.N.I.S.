#!/usr/bin/env bash
# Completa setup WSL JANIS — no apt obbligatorio
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
JANIS="${JANIS:-$HOME/projects/J.A.N.I.S.}"
BRAIN="$JANIS/packages/brain"
VENV="${JANIS_VENV:-$HOME/janis-venv}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2:2b}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$ROOT/infra/wsl/bootstrap-venv.sh"
bash "$ROOT/infra/wsl/install-ollama-user.sh" || echo "WARN ollama install"

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve > /tmp/ollama-serve.log 2>&1 &
  sleep 4
fi
ollama pull "$OLLAMA_MODEL" || true

cd "$BRAIN"
[ -f .env ] || cp .env.example .env
sed -i \
  -e "s|^JANIS_WORKSPACE=.*|JANIS_WORKSPACE=$HOME|" \
  -e "s|^JANIS_PROJECT_DIR=.*|JANIS_PROJECT_DIR=$BRAIN|" \
  -e "s|^JANIS_MONOREPO_ROOT=.*|JANIS_MONOREPO_ROOT=$JANIS|" \
  -e "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=$OLLAMA_MODEL|" \
  -e "s|^LOCAL_FIRST=.*|LOCAL_FIRST=true|" \
  -e "s|^CLOUD_LLM_ALLOWED=.*|CLOUD_LLM_ALLOWED=false|" \
  .env

cat > data/runtime.json <<'EOF'
{"paid_mode":false,"reasoning_provider":"ollama","cursor_reasoning_model":"","cursor_code_enabled":false,"openrouter_when_paid":false}
EOF

echo "JANIS_VENV=$VENV" > "$HOME/.janis-wsl.env"
echo "Setup OK. Avvia: bash $ROOT/infra/wsl/start-brain.sh"
