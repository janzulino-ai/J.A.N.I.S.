#!/usr/bin/env bash
# TESTER — ISO ibrida BIOS/UEFI da rootfs (live/rescue minimale)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
ROOTFS="$BUILD/rootfs"
ISO_DIR="$BUILD/iso"
OUT_DIR="$ROOT/out"
OUT_ISO="$OUT_DIR/janis-tester.iso"
THEME_SRC="$ROOT/../infra/grub/theme"

[ -d "$ROOTFS" ] || { echo "Esegui build-base.sh prima"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Esegui con sudo"; exit 1; }

for cmd in mksquashfs xorriso; do
  command -v "$cmd" >/dev/null || { echo "Manca $cmd — apt install squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin"; exit 1; }
done

rm -rf "$ISO_DIR"
mkdir -p "$ISO_DIR/live" "$ISO_DIR/boot/grub" "$OUT_DIR"

echo "=== squashfs ==="
mksquashfs "$ROOTFS" "$ISO_DIR/live/filesystem.squashfs" -comp xz -e boot || \
  mksquashfs "$ROOTFS" "$ISO_DIR/live/filesystem.squashfs" -comp xz

# Kernel + initrd dal rootfs
KVER="$(ls "$ROOTFS/boot/vmlinuz-"* 2>/dev/null | head -1 | sed 's|.*/vmlinuz-||' || true)"
if [ -n "${KVER:-}" ]; then
  cp -L "$ROOTFS/boot/vmlinuz-$KVER" "$ISO_DIR/live/vmlinuz"
  if [ -f "$ROOTFS/boot/initrd.img-$KVER" ]; then
    cp -L "$ROOTFS/boot/initrd.img-$KVER" "$ISO_DIR/live/initrd.img"
  else
    echo "WARN: initrd assente — ISO può non bootare live; usa come rescue/rootfs carrier"
    : > "$ISO_DIR/live/initrd.img"
  fi
else
  echo "WARN: nessun vmlinuz — completa install-packages.sh"
fi

# Tema GRUB
mkdir -p "$ISO_DIR/boot/grub/themes/janis"
if [ -d "$THEME_SRC" ]; then
  cp -r "$THEME_SRC/"* "$ISO_DIR/boot/grub/themes/janis/" 2>/dev/null || true
fi
# background.png prodotto in infra/grub/theme/ (HUD placeholder o asset artistico)
if [ ! -s "$ISO_DIR/boot/grub/themes/janis/background.png" ]; then
  echo "WARN: background.png assente/vuoto — vedi infra/grub/README.md checklist"
  : > "$ISO_DIR/boot/grub/themes/janis/background.png"
fi

cat > "$ISO_DIR/boot/grub/grub.cfg" <<'EOF'
set timeout=8
set default=0
insmod all_video
insmod gfxterm
terminal_output gfxterm
set theme=/boot/grub/themes/janis/theme.txt

menuentry "JANIS Safe Live / Rescue" {
  linux /live/vmlinuz boot=live components quiet splash
  initrd /live/initrd.img
}
menuentry "JANIS — info Live Distro / install" {
  echo "Live Distro: docs/LIVE-DISTRO.md — RAM min 16GB, consigliati 32GB"
  echo "Dopo kernel: neuron splash kiosk (non in GRUB)"
  echo "Install SSD: deploy-disk.sh (digitare WIPE) o Debian netinst"
  echo "Gate: docs/MODE-B-SSD2-GATE.md — nessun wipe automatico"
  sleep 10
}
menuentry "Boot from next disk" {
  exit
}
EOF

# README nel ISO
cat > "$ISO_DIR/JANIS-README.txt" <<'EOF'
JANIS Tester ISO
================
Live/rescue minimale. Per installare su SSD:
  1) Build rootfs: sudo bash TESTER/build-base.sh
  2) Deploy disco: sudo bash TESTER/deploy-disk.sh /dev/DISK --layout lvm
     (digitare WIPE — distruttivo)
  Oppure: Debian 12 netinst ufficiale + scripts/install-server.sh
EOF

# Anche tarball rootfs di backup
tar -C "$ROOTFS" -czf "$OUT_DIR/janis-tester.rootfs.tgz" .

echo "=== xorriso hybrid ISO ==="
# EFI eltorito opzionale se grub-mkrescue disponibile
if command -v grub-mkrescue >/dev/null 2>&1; then
  grub-mkrescue -o "$OUT_ISO" "$ISO_DIR" -- -volid JANIS_TESTER
else
  xorriso -as mkisofs \
    -r -V "JANIS_TESTER" \
    -o "$OUT_ISO" \
    -J -joliet-long \
    -b boot/grub/i386-pc/eltorito.img \
    -c boot/grub/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    "$ISO_DIR" 2>/dev/null || \
  xorriso -as mkisofs -r -V "JANIS_TESTER" -o "$OUT_ISO" -J "$ISO_DIR"
fi

ls -lh "$OUT_ISO" "$OUT_DIR/janis-tester.rootfs.tgz"
echo "OK: $OUT_ISO"
echo "Scrivi USB: sudo bash $ROOT/write-usb.sh /dev/sdX"
