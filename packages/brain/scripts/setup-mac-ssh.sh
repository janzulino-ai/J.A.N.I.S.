#!/usr/bin/env bash
# JANIS — configura SSH sul Mac per accesso da Windows (janzu@mac-mini-di-janzu.local)
# Esegui sul Mac: bash scripts/setup-mac-ssh.sh
# In Cursor Mac: apri terminale integrato nella cartella JANIS e lancia lo script.

set -euo pipefail

USER_NAME="${USER:-janzu}"
SSH_DIR="${HOME}/.ssh"
AUTH_KEYS="${SSH_DIR}/authorized_keys"

# Chiave pubblica Windows (JN-PC) — aggiorna se rigeneri ssh-keygen su Windows
WIN_PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ0XI0zzgJAU1Swjntbrg/AsIj1s4uPtBBLF/i/KgESM agenz@JN-PC'

# Opzionale: passa altra chiave come argomento o da clipboard
if [[ "${1:-}" == "--clipboard" ]] && command -v pbpaste >/dev/null; then
  CLIP="$(pbpaste | tr -d '\r' | head -1)"
  if [[ -n "$CLIP" && "$CLIP" == ssh-* ]]; then
    WIN_PUBKEY="$CLIP"
    echo "→ Chiave letta dagli appunti."
  fi
elif [[ -n "${1:-}" && "${1:-}" != "--clipboard" ]]; then
  WIN_PUBKEY="$1"
  echo "→ Chiave passata come argomento."
fi

echo "=== JANIS — setup SSH Mac ==="
echo "Utente: ${USER_NAME}"
echo "Host:   $(hostname)"
echo ""

mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"

touch "${AUTH_KEYS}"
chmod 600 "${AUTH_KEYS}"

FINGERPRINT="$(ssh-keygen -lf /dev/stdin <<< "${WIN_PUBKEY}" 2>/dev/null | awk '{print $2}' || true)"

if grep -qF "${WIN_PUBKEY}" "${AUTH_KEYS}" 2>/dev/null; then
  echo "✓ Chiave Windows già presente in authorized_keys ${FINGERPRINT:+($FINGERPRINT)}"
else
  echo "${WIN_PUBKEY}" >> "${AUTH_KEYS}"
  echo "✓ Chiave Windows aggiunta ${FINGERPRINT:+($FINGERPRINT)}"
fi

# Permessi corretti (macOS è rigido)
chown "${USER_NAME}:staff" "${SSH_DIR}" "${AUTH_KEYS}" 2>/dev/null || true
chmod 700 "${SSH_DIR}"
chmod 600 "${AUTH_KEYS}"

# Accesso remoto (SSH)
REMOTE_STATUS="$(sudo -n systemsetup -getremotelogin 2>/dev/null || systemsetup -getremotelogin 2>/dev/null || echo "Unknown")"
echo ""
echo "Accesso remoto: ${REMOTE_STATUS}"

if echo "${REMOTE_STATUS}" | grep -qi "Off"; then
  echo ""
  echo "⚠ Accesso remoto disattivato. Attivalo con:"
  echo "  sudo systemsetup -setremotelogin on"
  echo "  oppure Impostazioni → Generali → Condivisione → Accesso remoto"
  if sudo -n true 2>/dev/null; then
    echo "→ Provo ad attivare (sudo)..."
    sudo systemsetup -setremotelogin on && echo "✓ Accesso remoto attivato" || true
  fi
else
  echo "✓ Accesso remoto sembra attivo"
fi

# sshd: authorized_keys in home utente
if [[ -f /etc/ssh/sshd_config ]]; then
  if grep -q "^AuthorizedKeysFile" /etc/ssh/sshd_config; then
    echo "AuthorizedKeysFile: $(grep ^AuthorizedKeysFile /etc/ssh/sshd_config)"
  fi
fi

echo ""
echo "=== Test locale ==="
if ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no "${USER_NAME}@127.0.0.1" "echo OK locale" 2>/dev/null; then
  echo "✓ SSH locale OK"
else
  echo "— SSH locale non testato con chiave (normale se non hai chiave Mac→Mac)"
fi

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname)"

echo ""
echo "=== Da Windows (PowerShell) ==="
echo "  ssh ${USER_NAME}@${HOSTNAME_SHORT}.local"
if [[ -n "${LAN_IP}" ]]; then
  echo "  ssh ${USER_NAME}@${LAN_IP}"
fi
echo ""
echo "Cursor Remote SSH: ${USER_NAME}@${HOSTNAME_SHORT}.local"
echo ""
echo "Fatto."
