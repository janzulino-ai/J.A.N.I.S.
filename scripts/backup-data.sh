#!/usr/bin/env bash
# Backup data/ + identity/ — locale o da server remoto
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${1:-$ROOT/backups/janis-$STAMP}"
BRAIN_LOCAL="$ROOT/packages/brain"
REMOTE="${JANIS_SSH:-}"

mkdir -p "$DEST"

if [ -n "$REMOTE" ]; then
  REMOTE_BRAIN="${JANIS_REMOTE_BRAIN:-/home/janis/projects/J.A.N.I.S./packages/brain}"
  echo "Backup remoto $REMOTE:$REMOTE_BRAIN → $DEST"
  rsync -az "$REMOTE:$REMOTE_BRAIN/data/" "$DEST/data/"
  rsync -az "$REMOTE:$REMOTE_BRAIN/data/identity/" "$DEST/identity/" 2>/dev/null || true
else
  echo "Backup locale $BRAIN_LOCAL → $DEST"
  rsync -a "$BRAIN_LOCAL/data/" "$DEST/data/"
  rsync -a "$BRAIN_LOCAL/data/identity/" "$DEST/identity/" 2>/dev/null || true
fi

echo "OK → $DEST"
