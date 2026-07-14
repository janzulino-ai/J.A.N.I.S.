#!/usr/bin/env bash
# JANIS brain su WSL2 — setup local-only (Ollama, zero Cursor API)
# apt opzionale: continua anche se clock/apt fallisce
set -uo pipefail

JANIS_WIN="${JANIS_WIN:-/mnt/c/APP IA/JANIS}"
JANIS_LINK="${JANIS_LINK:-$HOME/projects/J.A.N.I.S.}"
BRAIN="$JANIS_LINK/packages/brain"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2:2b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "=== JANIS WSL setup ==="
echo "Repo link: $JANIS_LINK"
date

if [ ! -d "$JANIS_WIN/packages/brain" ]; then
  echo "ERRORE: monorepo non trovato in $JANIS_WIN"
  exit 1
fi

mkdir -p "$(dirname "$JANIS_LINK")"
if [ ! -e "$JANIS_LINK" ]; then
  ln -sfn "$JANIS_WIN" "$JANIS_LINK"
  echo "Symlink: $JANIS_LINK -> $JANIS_WIN"
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

echo "=== Dipendenze sistema (opzionale: APT=1 + sudo) ==="
if [ "${APT:-0}" = "1" ] && need_cmd sudo; then
  export DEBIAN_FRONTEND=noninteractive
  if ! sudo apt-get update -qq 2>/dev/null; then
    echo "WARN: apt update fallito (orologio sistema? fix: sudo hwclock -s oppure attendi ~1h)"
    echo "      Continuo senza apt — python/curl già presenti in WSL."
  else
    sudo apt-get install -y -qq \
      python3-venv python3-pip python3-dev jq git build-essential ffmpeg \
      2>/dev/null || true
  fi
else
  echo "Salto apt (default). Per jq/ffmpeg: APT=1 bash scripts/setup-wsl-brain.sh"
fi

for bin in python3 curl; do
  if ! need_cmd "$bin"; then
    echo "ERRORE: manca $bin"
    exit 1
  fi
done

echo "=== Ollama ==="
if ! need_cmd ollama; then
  echo "Installazione Ollama user-local (~/.local/bin)..."
  mkdir -p "$HOME/.local/bin"
  tmp=$(mktemp -d)
  if curl -fsSL "https://ollama.com/download/ollama-linux-amd64.tgz" -o "$tmp/ollama.tgz"; then
    tar -xzf "$tmp/ollama.tgz" -C "$HOME/.local"
    rm -rf "$tmp"
    export PATH="$HOME/.local/bin:$PATH"
    grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Ollama in ~/.local/bin"
  elif [ "${OLLAMA_SUDO:-0}" = "1" ]; then
    echo "Fallback: curl install.sh (sudo)..."
    curl -fsSL https://ollama.com/install.sh | sh || true
  else
    echo "WARN: scarica Ollama manualmente o: OLLAMA_SUDO=1 bash scripts/setup-wsl-brain.sh"
  fi
fi
export PATH="$HOME/.local/bin:${PATH:-}"

if need_cmd ollama; then
  if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "Avvio ollama serve..."
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 3
  fi
  echo "Pull $OLLAMA_MODEL (può richiedere minuti)..."
  ollama pull "$OLLAMA_MODEL" || ollama pull gemma2:2b || true
  ollama pull "$EMBED_MODEL" || true
  ollama list || true
else
  echo "WARN: ollama non in PATH — brain partirà ma LLM offline finché non installi Ollama"
fi

echo "=== venv brain ==="
cd "$BRAIN"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip wheel
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

sed -i \
  -e "s|^JANIS_WORKSPACE=.*|JANIS_WORKSPACE=$HOME|" \
  -e "s|^JANIS_PROJECT_DIR=.*|JANIS_PROJECT_DIR=$BRAIN|" \
  -e "s|^JANIS_MONOREPO_ROOT=.*|JANIS_MONOREPO_ROOT=$JANIS_LINK|" \
  -e "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://127.0.0.1:11434|" \
  -e "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=$OLLAMA_MODEL|" \
  -e "s|^LOCAL_FIRST=.*|LOCAL_FIRST=true|" \
  -e "s|^CLOUD_LLM_ALLOWED=.*|CLOUD_LLM_ALLOWED=false|" \
  -e "s|^LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" \
  -e "s|^AUTONOMY_AUTODEV_ENABLED=.*|AUTONOMY_AUTODEV_ENABLED=false|" \
  .env
grep -q '^LOCAL_FIRST=' .env || echo 'LOCAL_FIRST=true' >> .env
grep -q '^CLOUD_LLM_ALLOWED=' .env || echo 'CLOUD_LLM_ALLOWED=false' >> .env

mkdir -p data/memory data/chat data/identity

echo "=== runtime.json local-only ==="
cat > data/runtime.json <<'EOF'
{
  "paid_mode": false,
  "reasoning_provider": "ollama",
  "cursor_reasoning_model": "",
  "cursor_code_enabled": false,
  "openrouter_when_paid": false
}
EOF

echo "=== Smoke test ==="
python -c "import sys; sys.path.insert(0,'.'); from backend.main import app; print('import OK:', app.title)"
if curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "Ollama: OK"
else
  echo "WARN: Ollama non risponde su :11434"
fi

cat <<EOF

=== Setup completato ===
Avvio brain:
  bash $JANIS_LINK/infra/wsl/start-brain.sh

Verifica (senza jq):
  curl -s http://127.0.0.1:8001/api/status

Browser Windows:
  http://localhost:8001/server

EOF
