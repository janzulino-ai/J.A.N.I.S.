#!/usr/bin/env bash
set -euo pipefail
HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)
echo "Windows host IP: $HOST_IP"
if curl -sf -m 3 "http://${HOST_IP}:11434/api/tags" >/tmp/ollama-tags.json 2>/dev/null; then
  echo "Ollama su Windows host OK"
  cat /tmp/ollama-tags.json
  exit 0
fi
if curl -sf -m 3 http://127.0.0.1:11434/api/tags >/tmp/ollama-tags.json 2>/dev/null; then
  echo "Ollama su WSL localhost OK"
  cat /tmp/ollama-tags.json
  exit 0
fi
echo "NO_OLLAMA"
exit 1
