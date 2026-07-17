#!/usr/bin/env bash
# TESTER — debootstrap rootfs + packages.list + chroot-config
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
ROOTFS="$BUILD/rootfs"
RELEASE="${DEBIAN_RELEASE:-bookworm}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con sudo"
  exit 1
fi

mkdir -p "$BUILD"
if [ -d "$ROOTFS" ]; then
  echo "Rootfs esistente — usa BUILD_FORCE=1 per ricreare"
  [ "${BUILD_FORCE:-0}" = "1" ] || exit 0
  rm -rf "$ROOTFS"
fi

echo "=== debootstrap $RELEASE ==="
debootstrap --include=systemd,openssh-server,curl,ca-certificates,python3,python3-venv,sudo,apt-transport-https \
  "$RELEASE" "$ROOTFS" http://deb.debian.org/debian

# Mount essenziali per chroot apt
mount --bind /dev "$ROOTFS/dev"
mount --bind /dev/pts "$ROOTFS/dev/pts"
mount -t proc proc "$ROOTFS/proc"
mount -t sysfs sys "$ROOTFS/sys"
cleanup() {
  umount -l "$ROOTFS/dev/pts" 2>/dev/null || true
  umount -l "$ROOTFS/dev" 2>/dev/null || true
  umount -l "$ROOTFS/proc" 2>/dev/null || true
  umount -l "$ROOTFS/sys" 2>/dev/null || true
}
trap cleanup EXIT

export ROOTFS
bash "$ROOT/install-packages.sh"
bash "$ROOT/chroot-config.sh"

echo "OK: $ROOTFS — esegui verify-rootfs.sh"
