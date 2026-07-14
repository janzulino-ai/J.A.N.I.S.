#!/usr/bin/env bash
# TESTER — crea ISO ibride da rootfs
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
ROOTFS="$BUILD/rootfs"
OUT="$ROOT/out/janis-tester.iso"

[ -d "$ROOTFS" ] || { echo "Esegui build-base.sh prima"; exit 1; }
mkdir -p "$ROOT/out"

# Placeholder ISO — rootfs tar (fase 1); GRUB custom in fase 2
tar -C "$ROOTFS" -czf "$BUILD/rootfs.tgz" .
cp "$BUILD/rootfs.tgz" "$OUT.rootfs.tgz"
echo "Fase 1: rootfs archiviato in $OUT.rootfs.tgz"
echo "Fase 2 TODO: xorriso + GRUB janis theme → $OUT"
