#!/usr/bin/env bash
# Mount read-only inventario Windows (NTFS)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WIN_PART="${WIN_PART:-}"
MOUNT="${WIN_INVENTORY_MOUNT:-/mnt/janis-win-ro}"

if [[ -z "$WIN_PART" ]]; then
  eval "$("$ROOT/detect-win-disk.sh" 2>/dev/null | grep '^WIN_PART=')" || true
fi
if [[ -z "$WIN_PART" || ! -b "$WIN_PART" ]]; then
  echo "WIN_PART non trovato"
  exit 1
fi

sudo mkdir -p "$MOUNT"
if mountpoint -q "$MOUNT"; then
  sudo umount "$MOUNT" 2>/dev/null || true
fi
sudo mount -o ro,norecover "$WIN_PART" "$MOUNT" 2>/dev/null || \
  sudo ntfs-3g -o ro "$WIN_PART" "$MOUNT"

cat > /tmp/janis-mount-windows-ro <<'MOUNTSCRIPT'
#!/bin/sh
PART="${1:-/dev/nvme1n1p3}"
MNT="${2:-/mnt/janis-win-ro}"
mkdir -p "$MNT"
mount -o ro,norecover "$PART" "$MNT" 2>/dev/null || ntfs-3g -o ro "$PART" "$MNT"
MOUNTSCRIPT
sudo cp /tmp/janis-mount-windows-ro /usr/local/bin/janis-mount-windows-ro
sudo chmod +x /usr/local/bin/janis-mount-windows-ro
echo "Mount OK: $MOUNT"
ls "$MOUNT" | head -10
