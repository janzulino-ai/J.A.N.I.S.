#!/usr/bin/env bash
# Smoke Mode A: doctor + research/media endpoints se brain up.
set -euo pipefail
BRAIN_URL="${BRAIN_URL:-http://127.0.0.1:8001}"

echo "=== doctor ==="
if ! curl -sf -m 10 "$BRAIN_URL/api/doctor" -o /tmp/janis-doctor.json; then
  echo "FAIL: brain non raggiungibile su $BRAIN_URL"
  exit 1
fi
python3 - <<'PY'
import json
d=json.load(open("/tmp/janis-doctor.json"))
print("summary=", d.get("summary"), "ok=", d.get("ok"))
print("required_fail=", d.get("required_fail"))
print("optional_fail=", d.get("optional_fail"))
if d.get("summary") == "rosso":
    raise SystemExit(2)
PY

echo "=== media_status via tool registry (local import) ==="
# Prefer API status if brain alive
curl -sf -m 5 "$BRAIN_URL/api/status" >/dev/null && echo "api/status OK"

echo "Smoke doctor OK (non rosso). Avvia SearXNG/Comfy + MCP CLI per verde."
