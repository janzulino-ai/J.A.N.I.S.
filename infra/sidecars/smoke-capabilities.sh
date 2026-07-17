#!/usr/bin/env bash
# Smoke Mode A — delega a verify-mode-a.sh (plan A3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$ROOT/infra/sidecars/verify-mode-a.sh" "$@"
