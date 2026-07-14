#!/usr/bin/env bash
set -euo pipefail
JANIS="$HOME/projects/J.A.N.I.S."
BRAIN="$JANIS/packages/brain"
VENV="$HOME/janis-venv"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:latest}"
HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)

[ -f "$BRAIN/.env" ] || cp "$BRAIN/.env.example" "$BRAIN/.env"

OLLAMA_URL="http://127.0.0.1:11434"
for candidate in \
  "http://127.0.0.1:11434" \
  "http://$(ip route show default | awk '{print $3}')" \
  "http://$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)"
do
  if curl -sf -m 2 "${candidate}/api/tags" >/dev/null 2>&1; then
    OLLAMA_URL="$candidate"
    echo "Ollama: $OLLAMA_URL"
    break
  fi
done

sed -i \
  -e "s|^JANIS_WORKSPACE=.*|JANIS_WORKSPACE=$HOME|" \
  -e "s|^JANIS_PROJECT_DIR=.*|JANIS_PROJECT_DIR=$BRAIN|" \
  -e "s|^JANIS_MONOREPO_ROOT=.*|JANIS_MONOREPO_ROOT=$JANIS|" \
  -e "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=$OLLAMA_URL|" \
  -e "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=$OLLAMA_MODEL|" \
  -e "s|^LOCAL_FIRST=.*|LOCAL_FIRST=true|" \
  -e "s|^CLOUD_LLM_ALLOWED=.*|CLOUD_LLM_ALLOWED=false|" \
  -e "s|^LLM_PROVIDER=.*|LLM_PROVIDER=ollama|" \
  "$BRAIN/.env"

mkdir -p "$BRAIN/data/memory" "$BRAIN/data/chat" "$BRAIN/data/identity"
cat > "$BRAIN/data/runtime.json" <<'EOF'
{"paid_mode":false,"reasoning_provider":"ollama","cursor_reasoning_model":"","cursor_code_enabled":false,"openrouter_when_paid":false}
EOF

echo "JANIS_VENV=$VENV" > "$HOME/.janis-wsl.env"
echo "OLLAMA_BASE_URL=$OLLAMA_URL" >> "$HOME/.janis-wsl.env"
echo "Config OK"
