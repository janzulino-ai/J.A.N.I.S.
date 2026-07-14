#!/usr/bin/env bash
# Wrapper deploy — setup win-vm sul server
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec sudo bash "$ROOT/infra/win-vm/run-pending-setup.sh"
