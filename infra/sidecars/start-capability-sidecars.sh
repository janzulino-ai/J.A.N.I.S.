#!/usr/bin/env bash
# Avvia SearXNG (Docker) + ricorda ComfyUI Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE="$ROOT/infra/sidecars/docker-compose.searxng.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker non trovato — avvia SearXNG da Docker Desktop Windows:"
  echo "  docker compose -f infra/sidecars/docker-compose.searxng.yml up -d"
else
  echo "=== SearXNG ==="
  docker compose -f "$COMPOSE" up -d
  sleep 2
  curl -sf -m 5 http://127.0.0.1:8080/ >/dev/null && echo "SearXNG OK :8080" || echo "WARN: SearXNG non risponde ancora"
fi

echo ""
echo "=== ComfyUI ==="
if curl -sf -m 2 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo "ComfyUI già up :8188"
else
  echo "ComfyUI non raggiungibile su :8188"
  echo "Su Windows: infra/sidecars/install-comfyui-windows.ps1 -Start"
fi

echo ""
echo "Poi: bash $ROOT/infra/wsl/configure-sidecar-urls.sh"
