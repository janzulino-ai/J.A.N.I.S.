#!/usr/bin/env bash
# venv senza python3-venv (usa virtualenv.pyz)
set -euo pipefail
JANIS="${JANIS:-$HOME/projects/J.A.N.I.S.}"
BRAIN="$JANIS/packages/brain"
VENV="${JANIS_VENV:-$HOME/janis-venv}"

curl -fsSL https://bootstrap.pypa.io/virtualenv/virtualenv.pyz -o /tmp/virtualenv.pyz
python3 /tmp/virtualenv.pyz "$VENV"
"$VENV/bin/pip" install -q -U pip wheel
"$VENV/bin/pip" install -q -r "$BRAIN/requirements.txt"
cd "$BRAIN"
"$VENV/bin/python" -c "import sys; sys.path.insert(0,'.'); from backend.main import app; print('import OK:', app.title)"
echo "OK venv: $VENV"
