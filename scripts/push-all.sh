#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git add -A
if git diff --cached --quiet; then
  echo "Nessuna modifica da committare."
  exit 0
fi
MSG="${1:-JANIS: sync monorepo $(date +%Y-%m-%d)}"
git commit -m "$MSG"
BRANCH="${JANIS_BRANCH:-main}"
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Remote origin assente. Aggiungi: git remote add origin git@github.com:janzulino-ai/JANIS.git"
  exit 1
fi
if ! git push -u origin "$BRANCH" 2>/dev/null; then
  git push origin "$BRANCH" || { echo "Push fallito — crea repo janzulino-ai/JANIS su GitHub"; exit 1; }
fi
echo "Push OK → origin/$BRANCH"
echo "Tag opzionale: git tag brain@$(date +%Y.%m.%d) && git push --tags"
