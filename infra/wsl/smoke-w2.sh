#!/usr/bin/env bash
# W2 smoke — brain locale + chat + terminal HUD (no Cursor)
set -euo pipefail
BASE="${JANIS_BASE:-http://127.0.0.1:8001}"

echo "== status =="
curl -sf "$BASE/api/status" | head -c 200
echo ""

echo "== runtime local-first =="
curl -sf "$BASE/api/runtime" | grep -E 'cursor_code_enabled|paid_mode|reasoning_provider' || true

echo "== chat smoke =="
curl -sf -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' \
  -d '{"text":"rispondi solo: JANIS W2 OK"}' | head -c 300
echo ""

echo "== terminal HUD =="
curl -sf -X POST "$BASE/api/hud/terminal" \
  -H 'Content-Type: application/json' \
  -d '{"command":"echo JANIS_W2_TERMINAL","shell":"wsl"}' | head -c 300
echo ""

echo "== WS route (HTTP upgrade check) =="
curl -sf -o /dev/null -w "ws_janis HTTP %{http_code}\n" \
  "$BASE/ws/janis?device_id=smoke-w2" || true

echo ""
echo "W2 SMOKE OK"
