#!/usr/bin/env bash
# Ollama in ~/.local (no sudo) — richiede zstd (venv zstandard fallback)
set -euo pipefail
PREFIX="${OLLAMA_PREFIX:-$HOME/.local/ollama}"
mkdir -p "$PREFIX"
ARCHIVE="/tmp/ollama-linux-amd64.tar.zst"
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst -o "$ARCHIVE"
if tar --zstd -x -f "$ARCHIVE" -C "$PREFIX" 2>/dev/null; then
  :
elif command -v zstd >/dev/null; then
  zstd -d "$ARCHIVE" -o /tmp/ollama-linux-amd64.tar
  tar -x -f /tmp/ollama-linux-amd64.tar -C "$PREFIX"
elif [ -x "$HOME/janis-venv/bin/python" ]; then
  "$HOME/janis-venv/bin/python" - <<'PY'
import zstandard as zstd, tarfile, io, pathlib, os
archive = pathlib.Path("/tmp/ollama-linux-amd64.tar.zst")
prefix = pathlib.Path(os.environ.get("OLLAMA_PREFIX", os.path.expanduser("~/.local/ollama")))
prefix.mkdir(parents=True, exist_ok=True)
dctx = zstd.ZstdDecompressor()
with archive.open("rb") as f:
    with dctx.stream_reader(f) as reader:
        with tarfile.open(fileobj=io.BufferedReader(reader), mode="r|") as tar:
            tar.extractall(prefix)
print("extracted via python zstandard")
PY
else
  echo "ERRORE: serve zstd o janis-venv con zstandard. Oppure avvia Ollama Windows."
  exit 1
fi
OLLAMA_BIN=$(find "$PREFIX" -name ollama -type f 2>/dev/null | head -1)
if [ -z "$OLLAMA_BIN" ]; then
  echo "ERRORE: ollama binary non trovato in $PREFIX"
  exit 1
fi
mkdir -p "$HOME/.local/bin"
ln -sf "$OLLAMA_BIN" "$HOME/.local/bin/ollama"
export PATH="$HOME/.local/bin:$PATH"
grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
ollama --version
echo "OK ollama -> $HOME/.local/bin/ollama"
