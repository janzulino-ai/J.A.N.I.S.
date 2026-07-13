#!/usr/bin/env bash
# Auto-login tty1 → Chromium kiosk /server (solo 127.0.0.1)
set -euo pipefail

JANIS_HOME="${JANIS_HOME:-$HOME}"
BRAIN_DIR="${BRAIN_DIR:-$JANIS_HOME/projects/J.A.N.I.S./packages/brain}"

echo "=== Setup kiosk JANIS HDMI ==="

grep -q 'tty1' "$JANIS_HOME/.bash_profile" 2>/dev/null || cat >> "$JANIS_HOME/.bash_profile" <<'EOF'

# JANIS kiosk tty1
if [ "$(tty)" = "/dev/tty1" ] && [ -z "${DISPLAY:-}" ]; then
  exec startx
fi
EOF

cat > "$JANIS_HOME/.xinitrc" <<'EOF'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
chromium-browser --kiosk --noerrdialogs --disable-translate \
  --disk-cache-dir=/dev/null \
  http://127.0.0.1:8001/server &
wait
EOF
chmod +x "$JANIS_HOME/.xinitrc"

mkdir -p "$JANIS_HOME/.config/systemd/user"
cat > "$JANIS_HOME/.config/systemd/user/janis.service" <<EOF
[Unit]
Description=J.A.N.I.S. brain
After=network.target

[Service]
Type=simple
WorkingDirectory=$BRAIN_DIR
Environment=JANIS_PROJECT_DIR=$BRAIN_DIR
ExecStart=$BRAIN_DIR/.venv/bin/python run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

echo "Fatto. Avvia: systemctl --user enable --now janis"
echo "Kiosk: logout tty1 o reboot"
