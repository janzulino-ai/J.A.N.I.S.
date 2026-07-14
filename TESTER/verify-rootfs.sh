#!/usr/bin/env bash
# Verifica rootfs costruito in WSL (chroot, no boot reale)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="${ROOTFS:-$ROOT/build/rootfs}"

[ -d "$ROOTFS/bin" ] || { echo "FAIL: rootfs assente"; exit 1; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con sudo"
  exit 1
fi

fail=0
check() {
  local desc="$1"
  shift
  if "$@"; then
    echo "OK  $desc"
  else
    echo "FAIL $desc"
    fail=1
  fi
}

check "systemd presente" test -x "$ROOTFS/usr/lib/systemd/systemd"
check "kernel package" test -d "$ROOTFS/boot" -a -n "$(ls "$ROOTFS/boot/vmlinuz-"* 2>/dev/null | head -1)"
check "grub-efi" test -x "$ROOTFS/usr/sbin/grub-install"
check "utente janis" chroot "$ROOTFS" id janis
check "ssh server" test -x "$ROOTFS/usr/sbin/sshd"
check "python3" chroot "$ROOTFS" python3 --version
check "i3" test -x "$ROOTFS/usr/bin/i3"
check "chromium" test -x "$ROOTFS/usr/bin/chromium" -o -x "$ROOTFS/usr/bin/chromium-browser"
check "NetworkManager" test -x "$ROOTFS/usr/sbin/NetworkManager"
check "first-boot service" test -f "$ROOTFS/etc/systemd/system/janis-first-boot.service"

echo "--- dpkg stats ---"
chroot "$ROOTFS" dpkg -l | wc -l | xargs echo "pacchetti installati:"

if [ "$fail" -eq 0 ]; then
  echo "=== TUTTI I CHECK PASSATI ==="
else
  echo "=== ALCUNI CHECK FALLITI ==="
  exit 1
fi
