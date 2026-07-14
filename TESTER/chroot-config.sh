#!/usr/bin/env bash
# Configurazione post-debootstrap dentro build/rootfs
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ROOTFS="${ROOTFS:-$ROOT/build/rootfs}"
JANIS_USER="${JANIS_USER:-janis}"
JANIS_PASS="${JANIS_PASS:-janis}"
HOSTNAME="${HOSTNAME:-janis-server}"

[ -d "$ROOTFS/etc" ] || { echo "Rootfs mancante: $ROOTFS — esegui build-base.sh"; exit 1; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con sudo"
  exit 1
fi

echo "=== Locale / timezone ==="
echo "$HOSTNAME" > "$ROOTFS/etc/hostname"
cat > "$ROOTFS/etc/hosts" <<EOF
127.0.0.1   localhost
127.0.1.1   $HOSTNAME
::1         localhost ip6-localhost ip6-loopback
EOF

chroot "$ROOTFS" bash -c "
  export DEBIAN_FRONTEND=noninteractive
  ln -sf /usr/share/zoneinfo/Europe/Rome /etc/localtime
  echo 'it_IT.UTF-8 UTF-8' >> /etc/locale.gen
  locale-gen
  update-locale LANG=it_IT.UTF-8
"

echo "=== Utente $JANIS_USER ==="
if ! chroot "$ROOTFS" id "$JANIS_USER" &>/dev/null; then
  chroot "$ROOTFS" useradd -m -s /bin/bash -G sudo,audio,video,render "$JANIS_USER"
fi
echo "$JANIS_USER:$JANIS_PASS" | chroot "$ROOTFS" chpasswd
echo "$JANIS_USER ALL=(ALL) NOPASSWD:ALL" > "$ROOTFS/etc/sudoers.d/$JANIS_USER"
chmod 440 "$ROOTFS/etc/sudoers.d/$JANIS_USER"

echo "=== SSH ==="
sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' "$ROOTFS/etc/ssh/sshd_config"
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' "$ROOTFS/etc/ssh/sshd_config"
mkdir -p "$ROOTFS/etc/ssh/sshd_config.d"
echo "PasswordAuthentication yes" > "$ROOTFS/etc/ssh/sshd_config.d/99-janis.conf"

echo "=== NetworkManager ==="
mkdir -p "$ROOTFS/etc/NetworkManager/conf.d"
cat > "$ROOTFS/etc/NetworkManager/conf.d/janis.conf" <<'EOF'
[main]
plugins=ifupdown,keyfile
EOF

echo "=== i3 minimale per janis ==="
JANIS_HOME="$ROOTFS/home/$JANIS_USER"
mkdir -p "$JANIS_HOME/.config/i3"
cat > "$JANIS_HOME/.config/i3/config" <<'EOF'
set $mod Mod4
font pango monospace 10
floating_modifier $mod
bindsym $mod+Return exec alacritty
bindsym $mod+d exec rofi -show drun
bindsym $mod+Shift+q kill
bindsym $mod+Shift+e exec i3-msg exit
bar {
    status_command i3status
}
EOF
chown -R 1000:1000 "$JANIS_HOME/.config" 2>/dev/null || chroot "$ROOTFS" chown -R "$JANIS_USER:$JANIS_USER" "/home/$JANIS_USER/.config"

cat > "$JANIS_HOME/.xinitrc" <<'EOF'
#!/bin/sh
exec i3
EOF
chmod +x "$JANIS_HOME/.xinitrc"
chroot "$ROOTFS" chown "$JANIS_USER:$JANIS_USER" "/home/$JANIS_USER/.xinitrc"

mkdir -p "$ROOTFS/etc/lightdm/lightdm.conf.d"
cat > "$ROOTFS/etc/lightdm/lightdm.conf.d/janis.conf" <<EOF
[Seat:*]
autologin-user=$JANIS_USER
autologin-user-timeout=0
user-session=i3
EOF

echo "=== fstab template (UUID sostituiti da deploy-disk.sh) ==="
cat > "$ROOTFS/etc/fstab.janis-template" <<'EOF'
# UUID=EFI_UUID  /boot/efi  vfat  umask=0077  0  1
# UUID=BOOT_UUID /boot      ext4  defaults    0  2
# UUID=ROOT_UUID /          ext4  defaults    0  1
EOF

echo "=== GRUB defaults ==="
mkdir -p "$ROOTFS/etc/default"
if [ -f "$ROOT/../infra/grub/theme/theme.txt" ]; then
  mkdir -p "$ROOTFS/boot/grub/themes/janis"
  cp -r "$ROOT/../infra/grub/theme/"* "$ROOTFS/boot/grub/themes/janis/" 2>/dev/null || true
fi
cat > "$ROOTFS/etc/default/grub" <<'EOF'
GRUB_DEFAULT=0
GRUB_TIMEOUT=3
GRUB_DISTRIBUTOR="Debian"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""
GRUB_THEME=/boot/grub/themes/janis/theme.txt
EOF

echo "=== Post-boot script (NVIDIA + JANIS) ==="
mkdir -p "$ROOTFS/usr/local/sbin"
cat > "$ROOTFS/usr/local/sbin/janis-first-boot.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
MARKER=/var/lib/janis-first-boot.done
[ -f "$MARKER" ] && exit 0

if lspci 2>/dev/null | grep -qi nvidia; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq nvidia-driver firmware-misc-nonfree || true
fi

mkdir -p /home/janis/projects
chown janis:janis /home/janis/projects
touch "$MARKER"
EOF
chmod +x "$ROOTFS/usr/local/sbin/janis-first-boot.sh"

mkdir -p "$ROOTFS/etc/systemd/system"
cat > "$ROOTFS/etc/systemd/system/janis-first-boot.service" <<'EOF'
[Unit]
Description=JANIS first boot setup
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/var/lib/janis-first-boot.done

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/janis-first-boot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
chroot "$ROOTFS" systemctl enable janis-first-boot.service 2>/dev/null || \
  ln -sf /etc/systemd/system/janis-first-boot.service "$ROOTFS/etc/systemd/system/multi-user.target.wants/janis-first-boot.service"

echo "OK: chroot-config su $ROOTFS"
