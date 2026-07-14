#!/usr/bin/env bash
# Qdrant binario nativo (senza Docker)
set -euo pipefail
VERSION="${QDRANT_VERSION:-v1.12.5}"
INSTALL_DIR="${QDRANT_INSTALL:-$HOME/.local/qdrant}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ARCH_TAG=x86_64-unknown-linux-gnu ;;
  aarch64|arm64) ARCH_TAG=aarch64-unknown-linux-gnu ;;
  *) echo "Arch non supportata: $ARCH"; exit 1 ;;
esac

if [ -x "$INSTALL_DIR/qdrant" ]; then
  echo "Qdrant già installato: $INSTALL_DIR/qdrant"
  exit 0
fi

mkdir -p "$INSTALL_DIR"
tmp=$(mktemp -d)
url="https://github.com/qdrant/qdrant/releases/download/${VERSION}/qdrant-${ARCH_TAG}.tar.gz"
echo "Download $url"
curl -fsSL "$url" -o "$tmp/qdrant.tar.gz"
tar -xzf "$tmp/qdrant.tar.gz" -C "$INSTALL_DIR"
rm -rf "$tmp"
chmod +x "$INSTALL_DIR/qdrant"
echo "OK: $INSTALL_DIR/qdrant"
