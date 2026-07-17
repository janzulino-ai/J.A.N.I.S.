#!/usr/bin/env bash
# Installa CLI MCP capability in WSL (best-effort).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="${JANIS_VENV:-$HOME/janis-venv}"
PIP=""
if [ -x "$VENV/bin/pip" ]; then
  PIP="$VENV/bin/pip"
elif [ -x "$ROOT/packages/brain/.venv/bin/pip" ]; then
  PIP="$ROOT/packages/brain/.venv/bin/pip"
  VENV="$ROOT/packages/brain/.venv"
fi

BIN_DIR="${JANIS_MCP_BIN:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$VENV/bin:$PATH"

echo "=== MCP CLI install (PATH+=$BIN_DIR) ==="
if [ -n "$PIP" ]; then
  echo "pip: $PIP"
else
  echo "WARN: nessun venv — uso pip3 --user"
  PIP="pip3"
fi

try_pip() {
  local pkg="$1"
  echo "--- pip install $pkg ---"
  "$PIP" install -U "$pkg" 2>&1 | tail -n 5 || echo "FAIL: $pkg (continua)"
}

# Priorità doctor: codebase-memory
try_pip "codebase-memory-mcp" || true
# Docling MCP (nomi possibili upstream)
try_pip "docling-mcp" || try_pip "docling[mcp]" || true
# OfficeCLI
try_pip "officecli" || true

# Symlink helper se moduli espongono console_scripts nel venv
# docling package espone docling-mcp-server
if [ -x "$VENV/bin/docling-mcp-server" ]; then
  ln -sf "$VENV/bin/docling-mcp-server" "$BIN_DIR/docling-mcp"
  ln -sf "$VENV/bin/docling-mcp-server" "$BIN_DIR/docling-mcp-server"
  echo "link $BIN_DIR/docling-mcp → docling-mcp-server"
fi
for cmd in codebase-memory-mcp officecli; do
  if [ -x "$VENV/bin/$cmd" ] && [ ! -e "$BIN_DIR/$cmd" ]; then
    ln -sf "$VENV/bin/$cmd" "$BIN_DIR/$cmd"
    echo "link $BIN_DIR/$cmd"
  fi
done

# Agent-Reach (opzionale — clone se pip assente)
if ! command -v agent-reach >/dev/null 2>&1 && ! command -v reach >/dev/null 2>&1; then
  echo "--- agent-reach (opzionale) ---"
  try_pip "agent-reach" || echo "Installa manualmente: https://github.com/Panniantong/Agent-Reach"
fi

echo ""
echo "=== PATH check ==="
for cmd in codebase-memory-mcp docling-mcp officecli agent-reach reach; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "OK  $cmd → $(command -v "$cmd")"
  else
    echo "MISS $cmd"
  fi
done

echo ""
echo "Aggiungi a ~/.bashrc se serve:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "Poi: bash $ROOT/infra/wsl/configure-sidecar-urls.sh && riavvia brain"
