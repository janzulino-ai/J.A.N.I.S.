#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/janis-venv/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
exec "$HOME/janis-venv/bin/python" scripts/smoke_image_gen.py
