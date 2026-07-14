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

# ── Dipendenze audio (Firefox/WebKit) senza sudo ──
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

install_firefox_portable() {
  local dest="$JANIS_HOME/.local/firefox"
  if [ -x "$dest/firefox" ]; then
    echo "Firefox portable già presente"
    return 0
  fi
  echo "Download Firefox portable (open source, no sudo)..."
  mkdir -p "$JANIS_HOME/.local"
  tmp=$(mktemp -d)
  curl -fsSL "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US" -o "$tmp/firefox.tar.xz"
  tar -xJf "$tmp/firefox.tar.xz" -C "$JANIS_HOME/.local"
  rm -rf "$tmp"
  echo "Firefox → $JANIS_HOME/.local/firefox/firefox"
}

setup_firefox_kiosk() {
  local ff="$JANIS_HOME/.local/firefox"
  local profile="$JANIS_HOME/.janis-firefox-kiosk"
  mkdir -p "$ff/distribution"
  cp "$ROOT_KIOSK/firefox-policies.json" "$ff/distribution/policies.json"
  mkdir -p "$profile"
  if [ ! -f "$profile/prefs.js" ]; then
    cat > "$profile/prefs.js" <<'PREFS'
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("app.update.enabled", false);
user_pref("browser.startup.homepage", "http://127.0.0.1:8001/server");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
PREFS
  fi
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
install_firefox_portable || true
setup_firefox_kiosk || true

if can_pywebview_gtk; then
  echo "Kiosk shell: pywebview + WebKit GTK (open source)"
elif [ -x "$JANIS_HOME/.local/firefox/firefox" ]; then
  echo "Kiosk shell: Firefox kiosk (open source)"
else
  echo "WARN: installa dipendenze: sudo apt install gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-gi firefox"
fi

tty_hook='
# JANIS kiosk tty1
if [ -z "${DISPLAY:-}" ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
  exec startx
fi'

# ── launcher kiosk (pywebview GTK → Firefox → Chromium debian) ──
mkdir -p "$JANIS_HOME/.local/bin"
chmod +x "$KIOSK_PY" 2>/dev/null || true
cat > "$JANIS_HOME/.local/bin/janis-kiosk-browser" <<KIOSK
#!/bin/sh
export LD_LIBRARY_PATH="\$HOME/.local/lib-deps/usr/lib/x86_64-linux-gnu\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
BRAIN_PY="$BRAIN_VENV"
WEBVIEW_PY="$KIOSK_PY"
FIREFOX="\$HOME/.local/firefox/firefox"
PROFILE="\$HOME/.janis-firefox-kiosk"
CHROM_DEB=""
for c in /usr/bin/chromium /usr/bin/chromium-browser; do
  [ -x "\$c" ] && CHROM_DEB="\$c" && break
done

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  curl -sf http://127.0.0.1:8001/api/status >/dev/null 2>&1 && break
  sleep 2
done

# 1) Shell proprietaria open source: WebKit GTK (solo HUD /server)
if [ -x "\$BRAIN_PY" ] && [ -f "\$WEBVIEW_PY" ]; then
  if "\$BRAIN_PY" -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); import webview" 2>/dev/null; then
    exec "\$BRAIN_PY" "\$WEBVIEW_PY"
  fi
fi

# 2) Firefox open source — profilo kiosk, no account Google
if [ -x "\$FIREFOX" ]; then
  exec "\$FIREFOX" -no-remote -profile "\$PROFILE" -kiosk http://127.0.0.1:8001/server
fi

# 3) Chromium Debian (apt) — no Chrome for Testing / no sync Google
if [ -n "\$CHROM_DEB" ]; then
  exec "\$CHROM_DEB" --kiosk --no-first-run --disable-sync --guest \
    --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
    http://127.0.0.1:8001/server
fi

echo "Kiosk: mancano dipendenze open source" >&2
echo "sudo apt install -y gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-gi firefox chromium-browser xorg xinit" >&2
exec xterm -hold -e "echo JANIS kiosk: apt install gtk webkit firefox; sleep 120"
KIOSK
chmod +x "$JANIS_HOME/.local/bin/janis-kiosk-browser"

# ── .xinitrc ──
cat > "$JANIS_HOME/.xinitrc" <<XINIT
#!/bin/sh
exec >>"$JANIS_HOME/.janis-kiosk.log" 2>&1
echo "=== kiosk start \$(date) ==="
command -v xset >/dev/null && xset s off && xset -dpms && xset s noblank
exec "$JANIS_HOME/.local/bin/janis-kiosk-browser"
XINIT
chmod +x "$JANIS_HOME/.xinitrc"

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
echo "Kiosk:  login tty1 → HUD /server (pywebview WebKit o Firefox open source)"
echo "        sudo apt install gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-gi firefox chromium-browser"
if [ "$(loginctl show-user "$(whoami)" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo "WARN: per servizio sempre attivo: sudo loginctl enable-linger $USER"
fi
