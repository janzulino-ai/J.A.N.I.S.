#!/usr/bin/env bash
# Setup kiosk HDMI + janis.service (senza sudo dove possibile)
set -euo pipefail

JANIS_HOME="${JANIS_HOME:-$HOME}"
BRAIN_DIR="${BRAIN_DIR:-$JANIS_HOME/projects/J.A.N.I.S./packages/brain}"
MARKER="# JANIS kiosk tty1"

echo "=== Setup JANIS server ==="

# ── Browser (Firefox portable se chromium assente) ──
install_firefox_portable() {
  local dest="$JANIS_HOME/.local/firefox"
  if [ -x "$dest/firefox" ]; then
    echo "Firefox portable già presente"
    return 0
  fi
  echo "Download Firefox portable (no sudo)..."
  mkdir -p "$JANIS_HOME/.local"
  tmp=$(mktemp -d)
  curl -fsSL "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US" -o "$tmp/firefox.tar.xz"
  tar -xJf "$tmp/firefox.tar.xz" -C "$JANIS_HOME/.local"
  rm -rf "$tmp"
  echo "Firefox → $JANIS_HOME/.local/firefox/firefox"
}

find_browser() {
  for bin in \
    /usr/bin/chromium-browser \
    /usr/bin/chromium \
    /snap/bin/chromium \
    "$JANIS_HOME/.local/firefox/firefox"; do
    if [ -x "$bin" ]; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

BROWSER=$(find_browser) || true
if [ -z "${BROWSER:-}" ]; then
  install_firefox_portable || true
  BROWSER=$(find_browser) || BROWSER="$JANIS_HOME/.local/firefox/firefox"
fi
echo "Browser kiosk: $BROWSER"

# ── tty1 → startx (Ubuntu legge .profile, non .bash_profile) ──
tty_hook='
# JANIS kiosk tty1
if [ -z "${DISPLAY:-}" ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
  exec startx
fi'

for f in "$JANIS_HOME/.profile" "$JANIS_HOME/.bash_profile"; do
  touch "$f"
  if ! grep -qF "$MARKER" "$f" 2>/dev/null; then
    printf '\n%s\n%s\n' "$MARKER" "$tty_hook" >> "$f"
    echo "Hook tty1 → $f"
  fi
done

# ── .xinitrc ──
cat > "$JANIS_HOME/.xinitrc" <<XINIT
#!/bin/sh
xset s off
xset -dpms
xset s noblank

# Attendi brain
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf http://127.0.0.1:8001/api/status >/dev/null 2>&1 && break
  sleep 2
done

exec "$BROWSER" --kiosk --noerrdialogs \
  http://127.0.0.1:8001/server
XINIT
chmod +x "$JANIS_HOME/.xinitrc"

# ── janis.service (user) ──
mkdir -p "$JANIS_HOME/.config/systemd/user"
cat > "$JANIS_HOME/.config/systemd/user/janis.service" <<EOF
[Unit]
Description=J.A.N.I.S. brain
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BRAIN_DIR
Environment=JANIS_PROJECT_DIR=$BRAIN_DIR
Environment=HOME=$JANIS_HOME
ExecStart=$BRAIN_DIR/.venv/bin/python run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# ── @reboot senza linger (crontab) ──
CRON_CMD="@reboot sleep 20 && cd $BRAIN_DIR && JANIS_PROJECT_DIR=$BRAIN_DIR $BRAIN_DIR/.venv/bin/python run.py >> $JANIS_HOME/janis.log 2>&1 # JANIS"
( crontab -l 2>/dev/null | grep -v '# JANIS' || true
  echo "$CRON_CMD"
) | crontab -
echo "Crontab @reboot configurato"

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
echo "Kiosk:  login su tty1 (o reboot) → startx → Firefox/Chromium"
if [ ! -x "$BROWSER" ] 2>/dev/null; then
  echo "WARN: browser non trovato — riesegui dopo: sudo apt install chromium-browser"
fi
if [ "$(loginctl show-user "$(whoami)" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "WARN: per servizio sempre attivo: sudo loginctl enable-linger $USER"
fi
