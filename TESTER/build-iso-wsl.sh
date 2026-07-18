#!/usr/bin/env bash
# Build ISO da WSL. debootstrap NON può stare su /mnt/c (NTFS/DrvFs) — tar fallisce.
# Build su filesystem Linux (~/janis-iso-build), ISO finale copiata in cartella JANIS.
#
# Uso (da PowerShell, UNA riga alla volta — non incollare errori):
#   wsl -d Ubuntu
#   bash "/mnt/c/APP IA/JANIS/TESTER/build-iso-wsl.sh"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

# Directory nativa Linux (ext4). Override: JANIS_BUILD_HOME=/path
BUILD_HOME="${JANIS_BUILD_HOME:-$HOME/janis-iso-build}"
export BUILD="${BUILD:-$BUILD_HOME/TESTER/build}"
export ROOTFS="${ROOTFS:-$BUILD/rootfs}"
export OUT_DIR="${OUT_DIR:-$BUILD_HOME/TESTER/out}"

echo "Repo (sorgenti): $REPO"
echo "Build (Linux FS): $BUILD"
echo "ISO out:          $OUT_DIR"

case "$BUILD" in
  /mnt/*)
    echo "ERRORE: BUILD è su DrvFs ($BUILD)."
    echo "debootstrap/tar fallisce su /mnt/c. Usa BUILD sotto \$HOME (ext4)."
    exit 1
    ;;
esac

# Pulisci rootfs parziale lasciato su /mnt/c da tentativi precedenti
if [ -d "$REPO/TESTER/build/rootfs" ]; then
  echo "Rimuovo rootfs incompleto su DrvFs: $REPO/TESTER/build"
  sudo rm -rf "$REPO/TESTER/build" || true
fi

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  debootstrap debian-archive-keyring xorriso squashfs-tools \
  grub-pc-bin grub-efi-amd64-bin mtools dosfstools

mkdir -p "$BUILD" "$OUT_DIR"
cd "$REPO/TESTER"

# Script restano nel repo; BUILD/ROOTFS/OUT_DIR via env
sudo env BUILD="$BUILD" ROOTFS="$ROOTFS" OUT_DIR="$OUT_DIR" BUILD_FORCE=1 \
  bash build-base.sh
sudo env ROOTFS="$ROOTFS" bash verify-rootfs.sh
sudo env BUILD="$BUILD" ROOTFS="$ROOTFS" OUT_DIR="$OUT_DIR" \
  bash build-iso.sh

ISO_SRC="$OUT_DIR/janis-tester.iso"
[ -f "$ISO_SRC" ] || { echo "FAIL: ISO non creata in $ISO_SRC"; exit 1; }

# Copia su Windows (cartella JANIS)
mkdir -p "$REPO/TESTER/out"
cp -f "$ISO_SRC" "$REPO/TESTER/out/janis-tester.iso"
cp -f "$ISO_SRC" "$REPO/janis-tester.iso"

ls -lh "$ISO_SRC" "$REPO/janis-tester.iso"
echo "OK: $REPO/janis-tester.iso"
echo "OK: $REPO/TESTER/out/janis-tester.iso"
