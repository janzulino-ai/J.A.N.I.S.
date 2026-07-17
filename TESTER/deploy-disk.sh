#!/usr/bin/env bash
# Scrive rootfs su disco fisico (USB o SSD interno) + GRUB UEFI
# Uso: sudo bash deploy-disk.sh /dev/sdX [--layout simple|lvm] [--force]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="${ROOTFS:-$ROOT/build/rootfs}"
LAYOUT="${LAYOUT:-simple}"
FORCE=0

usage() {
  echo "Uso: sudo $0 /dev/sdX [--layout simple|lvm] [--force]"
  echo "  simple — EFI + /boot + ext4 /   (consigliato USB)"
  echo "  lvm    — EFI + /boot + LVM     (970 EVO Plus interno)"
  exit 1
}

DISK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --layout) LAYOUT="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage ;;
    *) DISK="$1"; shift ;;
  esac
done

[ -n "$DISK" ] || usage
[ -b "$DISK" ] || { echo "Non è un block device: $DISK"; exit 1; }
[ -d "$ROOTFS/etc" ] || { echo "Rootfs mancante — build-base.sh + chroot-config.sh"; exit 1; }
[ "$(id -u)" -ne 0 ] && { echo "Serve root"; exit 1; }

# Evita di formattare il disco WSL
ROOT_DEV="$(findmnt -no SOURCE / 2>/dev/null || true)"
if [[ "$DISK" == "${ROOT_DEV%%[0-9]*}" ]] || [[ "$ROOT_DEV" == "$DISK"* ]]; then
  echo "RIFIUTATO: $DISK sembra il disco di WSL/Windows"
  exit 1
fi

echo "=== ATTENZIONE ==="
echo "Disco: $DISK ($(lsblk -dn -o SIZE,MODEL "$DISK" 2>/dev/null || echo unknown))"
echo "Layout: $LAYOUT"
lsblk "$DISK"
if [ "$FORCE" -ne 1 ]; then
  read -r -p "TUTTI I DATI SU $DISK SARANNO CANCELLATI. Digita WIPE per continuare: " ans
  [ "$ans" = "WIPE" ] || { echo "Annullato."; exit 1; }
fi

wipefs -a "$DISK"
partprobe "$DISK" 2>/dev/null || true
sleep 1

MNT="$ROOT/build/mnt"
mkdir -p "$MNT"
cleanup() {
  umount -R "$MNT" 2>/dev/null || true
  if [ "$LAYOUT" = "lvm" ]; then
    lvchange -an janis-vg 2>/dev/null || true
    vgchange -an janis-vg 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [ "$LAYOUT" = "simple" ]; then
  parted -s "$DISK" mklabel gpt
  parted -s "$DISK" mkpart EFI fat32 1MiB 513MiB
  parted -s "$DISK" set 1 esp on
  parted -s "$DISK" mkpart boot ext4 513MiB 2561MiB
  parted -s "$DISK" mkpart root ext4 2561MiB 100%
  partprobe "$DISK"
  sleep 1

  EFI="${DISK}1"
  BOOT="${DISK}2"
  ROOT_PART="${DISK}3"
  [[ "$DISK" == /dev/nvme* ]] && EFI="${DISK}p1" BOOT="${DISK}p2" ROOT_PART="${DISK}p3"

  mkfs.vfat -F32 -n JANIS-EFI "$EFI"
  mkfs.ext4 -F -L janis-boot "$BOOT"
  mkfs.ext4 -F -L janis-root "$ROOT_PART"

  mount "$ROOT_PART" "$MNT"
  mkdir -p "$MNT/boot/efi" "$MNT/boot"
  mount "$BOOT" "$MNT/boot"
  mount "$EFI" "$MNT/boot/efi"

elif [ "$LAYOUT" = "lvm" ]; then
  parted -s "$DISK" mklabel gpt
  parted -s "$DISK" mkpart EFI fat32 1MiB 513MiB
  parted -s "$DISK" set 1 esp on
  parted -s "$DISK" mkpart boot ext4 513MiB 2561MiB
  parted -s "$DISK" mkpart lvm 2561MiB 100%
  partprobe "$DISK"
  sleep 1

  EFI="${DISK}1"
  BOOT="${DISK}2"
  LVM_PART="${DISK}3"
  [[ "$DISK" == /dev/nvme* ]] && EFI="${DISK}p1" BOOT="${DISK}p2" LVM_PART="${DISK}p3"

  mkfs.vfat -F32 -n JANIS-EFI "$EFI"
  mkfs.ext4 -F -L janis-boot "$BOOT"
  pvcreate -ff -y "$LVM_PART"
  vgcreate janis-vg "$LVM_PART"
  lvcreate -L 60G -n root janis-vg
  lvcreate -L 80G -n swap janis-vg
  lvcreate -l 100%FREE -n home janis-vg

  mkfs.ext4 -F -L janis-root /dev/janis-vg/root
  mkswap -L janis-swap /dev/janis-vg/swap
  mkfs.ext4 -F -L janis-home /dev/janis-vg/home

  mount /dev/janis-vg/root "$MNT"
  mkdir -p "$MNT/boot/efi" "$MNT/boot" "$MNT/home"
  mount "$BOOT" "$MNT/boot"
  mount "$EFI" "$MNT/boot/efi"
  mount /dev/janis-vg/home "$MNT/home"
else
  echo "Layout sconosciuto: $LAYOUT"
  exit 1
fi

echo "=== Copia rootfs (rsync) ==="
rsync -aHAX --info=progress2 --exclude=/boot/efi --exclude=/boot/vmlinuz* \
  "$ROOTFS/" "$MNT/"

echo "=== fstab ==="
EFI_UUID=$(blkid -s UUID -o value "$MNT/boot/efi")
BOOT_UUID=$(blkid -s UUID -o value "$MNT/boot")
if [ "$LAYOUT" = "simple" ]; then
  ROOT_UUID=$(blkid -s UUID -o value "$MNT")
  cat > "$MNT/etc/fstab" <<EOF
UUID=$EFI_UUID  /boot/efi  vfat  umask=0077       0  1
UUID=$BOOT_UUID /boot      ext4  defaults         0  2
UUID=$ROOT_UUID /          ext4  defaults,noatime 0  1
EOF
else
  ROOT_UUID=$(blkid -s UUID -o value /dev/janis-vg/root)
  HOME_UUID=$(blkid -s UUID -o value /dev/janis-vg/home)
  SWAP_UUID=$(blkid -s UUID -o value /dev/janis-vg/swap)
  cat > "$MNT/etc/fstab" <<EOF
UUID=$EFI_UUID  /boot/efi  vfat  umask=0077       0  1
UUID=$BOOT_UUID /boot      ext4  defaults         0  2
UUID=$ROOT_UUID /          ext4  defaults,noatime 0  1
UUID=$HOME_UUID /home      ext4  defaults,noatime 0  2
UUID=$SWAP_UUID none       swap  sw               0  0
EOF
fi

echo "=== GRUB in chroot ==="
mount --bind /dev "$MNT/dev"
mount --bind /proc "$MNT/proc"
mount --bind /sys "$MNT/sys"
mount --bind /run "$MNT/run" 2>/dev/null || mount -t tmpfs tmpfs "$MNT/run"

chroot "$MNT" bash -c "
  export DEBIAN_FRONTEND=noninteractive
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Debian --removable
  update-grub
"

echo "=== Deploy completato su $DISK ==="
lsblk "$DISK"
