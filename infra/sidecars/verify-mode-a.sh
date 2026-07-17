#!/usr/bin/env bash
# Mode A — verify sidecar stack (plan A3).
# Prerequisiti: Ollama + brain WSL + (opz.) SearXNG/Comfy/MCP CLI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAIN_URL="${BRAIN_URL:-http://127.0.0.1:8001}"
VENV="${JANIS_VENV:-$HOME/janis-venv}"
PY="${PYTHON:-$VENV/bin/python}"

echo "=== Mode A verify ==="
echo "Repo: $ROOT"
echo "Brain: $BRAIN_URL"

if ! curl -sf -m 5 "$BRAIN_URL/api/status" >/dev/null; then
  echo "FAIL: avvia brain (infra/wsl/start-brain.sh)"
  exit 1
fi

echo ""
echo "--- doctor (HTTP) ---"
curl -sf -m 15 "$BRAIN_URL/api/doctor" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('summary=', d.get('summary'))
print('required_fail=', d.get('required_fail'))
print('optional_fail=', len(d.get('optional_fail') or []))
if d.get('summary')=='rosso' or d.get('required_fail'):
    sys.exit(2)
"

echo ""
echo "--- capabilities ---"
curl -sf -m 10 "$BRAIN_URL/api/capabilities?wave=1" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('summary=', d.get('summary'), 'wave=', d.get('wave'))
for c in d.get('capabilities') or []:
    print(' ', c.get('id'), c.get('status'), 'e2e='+str(c.get('e2e')))
"

echo ""
echo "--- tool smoke (Python) ---"
export BRAIN_URL
export PYTHONPATH="$ROOT/packages/brain"
if [ -x "$PY" ]; then
  "$PY" "$ROOT/packages/brain/scripts/verify_mode_a.py" || {
    code=$?
    [ "$code" -eq 2 ] && echo "Doctor rosso — vedi SIDECARS-INSTALL.md" && exit 2
    exit "$code"
  }
else
  echo "WARN: venv non trovato ($PY) — solo check HTTP ok"
fi

echo ""
echo "Mode A verify OK. Per verde pieno:"
echo "  1) bash infra/sidecars/install-mcp-clis.sh"
echo "  2) bash infra/sidecars/start-capability-sidecars.sh"
echo "  3) bash infra/wsl/configure-sidecar-urls.sh && riavvia brain"
