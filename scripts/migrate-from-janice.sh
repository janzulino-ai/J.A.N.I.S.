#!/usr/bin/env bash
# Copia aggiornamenti da JANICE / JANICE-Pocket legacy (solo se esistono)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_BRAIN="${1:-$HOME/Documents/JANICE}"
SRC_POCKET="${2:-$HOME/Documents/JANICE-Pocket}"
rsync -a --exclude .git --exclude .venv --exclude __pycache__ \
  "$SRC_BRAIN/" "$ROOT/packages/brain/" 2>/dev/null || true
rsync -a --exclude .git --exclude .derivedData --exclude .spm \
  "$SRC_POCKET/" "$ROOT/apps/pocket/" 2>/dev/null || true
python3 "$ROOT/scripts/rename_to_janis.py"
echo "Migrate OK → $ROOT"
