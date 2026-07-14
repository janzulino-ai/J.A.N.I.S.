#!/usr/bin/env bash
# TESTER — debootstrap rootfs minimale Debian
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

debootstrap --include=systemd,openssh-server,curl,ca-certificates,python3,python3-venv,sudo \
  "$RELEASE" "$ROOTFS" http://deb.debian.org/debian

# Utente janis
chroot "$ROOTFS" useradd -m -s /bin/bash janis || true
echo "janis:janis" | chroot "$ROOTFS" chpasswd

# Hostname
echo janis-tester > "$ROOTFS/etc/hostname"

echo "OK: $ROOTFS"
