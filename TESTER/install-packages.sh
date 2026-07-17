#!/usr/bin/env bash
# Installa config/packages.list nel rootfs (post-debootstrap).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="${ROOTFS:-$ROOT/build/rootfs}"
PKG_LIST="$ROOT/config/packages.list"
RELEASE="${DEBIAN_RELEASE:-bookworm}"

[ -d "$ROOTFS/etc" ] || { echo "Rootfs mancante — esegui build-base.sh"; exit 1; }
[ -f "$PKG_LIST" ] || { echo "Manca $PKG_LIST"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Esegui con sudo"; exit 1; }

# Abilita non-free / contrib per firmware
cat > "$ROOTFS/etc/apt/sources.list" <<EOF
deb http://deb.debian.org/debian $RELEASE main contrib non-free non-free-firmware
deb http://deb.debian.org/debian $RELEASE-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security $RELEASE-security main contrib non-free non-free-firmware
EOF

# Filtra commenti / vuoti → file per chroot
BUILD_DIR="$(dirname "$ROOTFS")"
PKG_FILE="$BUILD_DIR/packages.filtered"
mkdir -p "$ROOTFS/tmp"
grep -vE '^\s*#|^\s*$' "$PKG_LIST" | tr -d '\r' > "$PKG_FILE"
COUNT="$(wc -l < "$PKG_FILE" | tr -d ' ')"
echo "=== apt-get install $COUNT pacchetti ==="
cp "$PKG_FILE" "$ROOTFS/tmp/packages.filtered"

chroot "$ROOTFS" bash -c '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  xargs -a /tmp/packages.filtered apt-get install -y -qq
'

echo "OK: packages installati in $ROOTFS"
