#!/usr/bin/env bash
# Setup kiosk HDMI + janis.service (senza sudo dove possibile)
set -euo pipefail

JANIS_HOME="${JANIS_HOME:-$HOME}"
BRAIN_DIR="${BRAIN_DIR:-$JANIS_HOME/projects/J.A.N.I.S./packages/brain}"
MARKER="# JANIS kiosk tty1"

echo "=== Setup JANIS server ==="

ROOT_KIOSK="$(cd "$(dirname "$0")" && pwd)"
BRAIN_VENV="$BRAIN_DIR/.venv/bin/python"
KIOSK_PY="$ROOT_KIOSK/janis-kiosk-webview.py"

# ── Dipendenze audio (WebKit/Chromium) senza sudo ──
install_libasound_user() {
  local dest="$JANIS_HOME/.local/lib-deps"
  if [ -f "$dest/usr/lib/x86_64-linux-gnu/libasound.so.2" ]; then
    return 0
  fi
  echo "Install libasound2 (user, no sudo)..."
  tmp=$(mktemp -d)
  ( cd "$tmp" && apt-get download libasound2t64 2>/dev/null || apt-get download libasound2 )
  deb=$(ls "$tmp"/*.deb 2>/dev/null | head -1)
  if [ -n "$deb" ]; then
    mkdir -p "$dest"
    dpkg-deb -x "$deb" "$dest"
  fi
  rm -rf "$tmp"
}

can_chromium() {
  for c in /snap/bin/chromium /usr/bin/chromium /usr/bin/chromium-browser; do
    [ -x "$c" ] && echo "$c" && return 0
  done
  return 1
}

setup_chromium_kiosk() {
  local profile="$JANIS_HOME/snap/chromium/common/janis-hud-kiosk"
  mkdir -p "$profile" "$JANIS_HOME/.config/janis-chromium-kiosk"
  chmod 700 "$profile" "$JANIS_HOME/.config/janis-chromium-kiosk" 2>/dev/null || true
}

can_pywebview_gtk() {
  "$BRAIN_VENV" -c "
import gi
gi.require_version('Gtk','3.0')
gi.require_version('WebKit2','4.1')
import webview
" 2>/dev/null
}

install_libasound_user || true
setup_chromium_kiosk || true

if CHROM=$(can_chromium); then
  echo "Kiosk shell: Chromium kiosk ($CHROM)"
elif can_pywebview_gtk; then
  echo "Kiosk shell: pywebview + WebKit GTK (fallback)"
else
  echo "WARN: installa dipendenze: sudo apt install chromium-browser xorg xinit"
fi

tty_hook='
# JANIS kiosk tty1
if [ -z "${DISPLAY:-}" ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
  exec startx
fi'

# ── launcher kiosk (pywebview GTK → Chromium) ──
mkdir -p "$JANIS_HOME/.local/bin"
chmod +x "$KIOSK_PY" 2>/dev/null || true
cat > "$JANIS_HOME/.local/bin/janis-kiosk-browser" <<KIOSK
#!/bin/sh
export LD_LIBRARY_PATH="\$HOME/.local/lib-deps/usr/lib/x86_64-linux-gnu\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
BRAIN_PY="$BRAIN_VENV"
WEBVIEW_PY="$KIOSK_PY"
HUD_URL="http://127.0.0.1:8001/server?v=hudfull01"
CHROM_DEB=""
for c in /snap/bin/chromium /usr/bin/chromium /usr/bin/chromium-browser; do
  [ -x "\$c" ] && CHROM_DEB="\$c" && break
done

# Profilo snap-compatible (evita SingletonLock EPERM)
if [ -x /snap/bin/chromium ]; then
  CHROM_PROFILE="\$HOME/snap/chromium/common/janis-hud-kiosk"
  CHROM_LAUNCH="/snap/bin/chromium"
else
  CHROM_PROFILE="\$HOME/.config/janis-chromium-kiosk"
  CHROM_LAUNCH="\$CHROM_DEB"
fi

# Risoluzione schermo primario
SCREEN_W="1920"
SCREEN_H="1080"
if command -v xrandr >/dev/null 2>&1; then
  OUT=\$(xrandr --current 2>/dev/null | awk '/ connected/{print \$1; exit}')
  if [ -n "\$OUT" ]; then
    PREF=\$(xrandr --current 2>/dev/null | awk -v o="\$OUT" '\$1==o {f=1} f&&/1920x1080/{print \$1; exit}')
    CUR=\$(xrandr --current 2>/dev/null | awk -v o="\$OUT" '\$1==o {f=1} f&&/\\*/{print \$1; exit}')
    MODE="\${PREF:-\$CUR}"
    if [ -n "\$MODE" ]; then
      xrandr --output "\$OUT" --mode "\$MODE" --primary 2>/dev/null || xrandr --output "\$OUT" --auto --primary 2>/dev/null || true
      SCREEN_W=\${MODE%x*}
      SCREEN_H=\${MODE#*x}
    fi
  fi
fi

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  curl -sf http://127.0.0.1:8001/api/status >/dev/null 2>&1 && break
  sleep 2
done

# 1) Chromium — motore kiosk principale
if [ -n "\$CHROM_LAUNCH" ]; then
  mkdir -p "\$CHROM_PROFILE"
  chmod 700 "\$CHROM_PROFILE" 2>/dev/null || true
  rm -f "\$CHROM_PROFILE/SingletonLock" "\$CHROM_PROFILE/SingletonSocket" 2>/dev/null || true
  CH_ARGS="--user-data-dir=\$CHROM_PROFILE"
  CH_ARGS="\$CH_ARGS --kiosk --no-first-run --disable-sync --no-default-browser-check"
  CH_ARGS="\$CH_ARGS --noerrdialogs --disable-infobars --disable-session-crashed-bubble"
  CH_ARGS="\$CH_ARGS --disable-features=TranslateUI,MediaRouter"
  CH_ARGS="\$CH_ARGS --start-fullscreen --window-size=\${SCREEN_W},\${SCREEN_H}"
  CH_ARGS="\$CH_ARGS --window-position=0,0 --force-device-scale-factor=1"
  CH_ARGS="\$CH_ARGS --disable-pinch --overscroll-history-navigation=0 --disable-gpu-compositing"
  # shellcheck disable=SC2086
  exec "\$CHROM_LAUNCH" \$CH_ARGS "\$HUD_URL"
fi

# 2) Fallback: WebKit GTK (solo HUD /server)
if [ -x "\$BRAIN_PY" ] && [ -f "\$WEBVIEW_PY" ]; then
  if "\$BRAIN_PY" -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); import webview" 2>/dev/null; then
    exec "\$BRAIN_PY" "\$WEBVIEW_PY"
  fi
fi

echo "Kiosk: manca Chromium" >&2
echo "sudo apt install -y chromium-browser xorg xinit" >&2
exec xterm -hold -e "echo JANIS kiosk: apt install chromium-browser; sleep 120"
KIOSK
chmod +x "$JANIS_HOME/.local/bin/janis-kiosk-browser"

# ── .xinitrc ──
cat > "$JANIS_HOME/.xinitrc" <<XINIT
#!/bin/sh
exec >>"$JANIS_HOME/.janis-kiosk.log" 2>&1
echo "=== kiosk start \$(date) ==="
command -v xset >/dev/null && xset s off && xset -dpms && xset s noblank
# Allinea output connesso (Unknown-1 / HDMI) — preferisci 1920x1080
if command -v xrandr >/dev/null 2>&1; then
  OUT=\$(xrandr 2>/dev/null | awk '/ connected/{print \$1; exit}')
  if [ -n "\$OUT" ]; then
    PREF=\$(xrandr 2>/dev/null | awk -v o="\$OUT" '\$1==o {f=1} f&&/1920x1080/{print \$1; exit}')
    CUR=\$(xrandr 2>/dev/null | awk -v o="\$OUT" '\$1==o {f=1} f&&/\\*/{print \$1; exit}')
    MODE="\${PREF:-\$CUR}"
    if [ -n "\$MODE" ]; then
      xrandr --output "\$OUT" --mode "\$MODE" --primary 2>/dev/null || xrandr --output "\$OUT" --auto --primary 2>/dev/null || true
      echo "xrandr: \$OUT @ \$MODE"
    fi
  fi
fi
exec "$JANIS_HOME/.local/bin/janis-kiosk-browser"
XINIT
chmod +x "$JANIS_HOME/.xinitrc"

# ── systemd user: kiosk auto-restart ──
UNIT_DIR="$JANIS_HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$JANIS_HOME/.local/bin/janis-kiosk-watchdog" <<'WDOG'
#!/bin/sh
# Riavvia Chromium se X è attivo; altrimenti attende login tty1 (startx via .profile)
HUD_URL="http://127.0.0.1:8001/server?v=hudfull01"
LOG="$HOME/.janis-kiosk.log"

while true; do
  if curl -sf http://127.0.0.1:8001/api/status >/dev/null 2>&1; then
    if pgrep -x Xorg >/dev/null 2>&1; then
      if ! pgrep -f "chromium.*8001/server" >/dev/null 2>&1; then
        echo "=== watchdog chromium restart $(date) ===" >>"$LOG"
        export DISPLAY="${DISPLAY:-:0}"
        rm -f "$HOME/snap/chromium/common/janis-hud-kiosk/SingletonLock" \
              "$HOME/snap/chromium/common/janis-hud-kiosk/SingletonSocket" 2>/dev/null
        exec "$HOME/.local/bin/janis-kiosk-browser"
      fi
    fi
  fi
  sleep 15
done
WDOG
chmod +x "$JANIS_HOME/.local/bin/janis-kiosk-watchdog"

cat > "$UNIT_DIR/janis-kiosk.service" <<EOF
[Unit]
Description=JANIS HUD kiosk watchdog (Chromium on :0)
After=janis.service network-online.target
Wants=janis.service

[Service]
Type=simple
Environment=HOME=$JANIS_HOME
Environment=DISPLAY=:0
ExecStart=$JANIS_HOME/.local/bin/janis-kiosk-watchdog
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat > "$JANIS_HOME/.local/bin/janis-kiosk-restart" <<'RESTART'
#!/bin/sh
systemctl --user restart janis.service 2>/dev/null || true
pkill -f "chromium.*8001/server" 2>/dev/null || true
rm -f "$HOME/snap/chromium/common/janis-hud-kiosk/SingletonLock" \
      "$HOME/snap/chromium/common/janis-hud-kiosk/SingletonSocket" 2>/dev/null
if pgrep -x Xorg >/dev/null 2>&1; then
  export DISPLAY="${DISPLAY:-:0}"
  nohup "$HOME/.local/bin/janis-kiosk-browser" >>"$HOME/.janis-kiosk.log" 2>&1 &
else
  echo "X non attivo: login su tty1 (Ctrl+Alt+F1) per avviare startx" >>"$HOME/.janis-kiosk.log"
fi
systemctl --user restart janis-kiosk.service 2>/dev/null || true
RESTART
chmod +x "$JANIS_HOME/.local/bin/janis-kiosk-restart"
systemctl --user daemon-reload 2>/dev/null || true
systemctl --user enable janis-kiosk.service 2>/dev/null || true

# ── tty1 hook (senza doppioni) ──
for f in "$JANIS_HOME/.profile" "$JANIS_HOME/.bash_profile"; do
  touch "$f"
  if grep -qF "$MARKER" "$f" 2>/dev/null; then
    # rimuovi blocchi duplicati precedenti
    python3 <<PY || true
from pathlib import Path
marker = "$MARKER"
for name in [".profile", ".bash_profile"]:
    p = Path("$JANIS_HOME") / name
    if not p.exists():
        continue
    lines = p.read_text().splitlines()
    out, skip = [], False
    for line in lines:
        if marker in line:
            skip = True
            continue
        if skip:
            if line.strip() == "fi":
                skip = False
            continue
        out.append(line)
    p.write_text("\n".join(out).rstrip() + "\n")
PY
  fi
  if ! grep -qF "$MARKER" "$f" 2>/dev/null; then
    printf '\n%s\n%s\n' "$MARKER" "$tty_hook" >> "$f"
    echo "Hook tty1 → $f"
  fi
done

# ── janis.service (user) — gestito da infra/sidecars/setup-systemd-user.sh ──
# Crontab @reboot rimosso: conflittava con systemd (porta 8001)
crontab -l 2>/dev/null | grep -v '# JANIS' | crontab - 2>/dev/null || true
echo "Crontab @reboot JANIS rimosso (usa systemd)"

# ── script avvio manuale ──
cat > "$JANIS_HOME/projects/J.A.N.I.S./scripts/start-janis.sh" <<'START'
#!/usr/bin/env bash
BRAIN="$HOME/projects/J.A.N.I.S./packages/brain"
cd "$BRAIN"
export JANIS_PROJECT_DIR="$BRAIN"
exec "$BRAIN/.venv/bin/python" run.py
START
chmod +x "$JANIS_HOME/projects/J.A.N.I.S./scripts/start-janis.sh"

echo ""
echo "=== Fatto ==="
echo "Brain:  systemctl --user enable --now janis"
echo "        oppure: ~/projects/J.A.N.I.S./scripts/start-janis.sh"
echo "Kiosk:  systemctl --user restart janis-kiosk  (o login tty1)"
echo "        janis-kiosk-restart"
if [ "$(loginctl show-user "$(whoami)" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "WARN: per servizio sempre attivo: sudo loginctl enable-linger $USER"
fi
