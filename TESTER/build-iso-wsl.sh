#!/usr/bin/env bash
# Build ISO da WSL (senza PowerShell). Uso:
#   wsl -d Ubuntu
#   bash "/mnt/c/APP IA/JANIS/TESTER/build-iso-wsl.sh"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Repo: $ROOT"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools
cd "$ROOT/TESTER"
sudo BUILD_FORCE=1 bash build-base.sh
sudo bash verify-rootfs.sh
sudo bash build-iso.sh
ls -lh out/janis-tester.iso "$ROOT/janis-tester.iso"
echo "OK: $ROOT/janis-tester.iso"
