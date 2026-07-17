#!/usr/bin/env bash
# Scrive out/janis-tester.iso su chiavetta USB (DISTRUTTIVO per il device).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ISO="${ISO:-$ROOT/out/janis-tester.iso}"
DEV="${1:-}"

if [ -z "$DEV" ]; then
  echo "Uso: sudo bash write-usb.sh /dev/sdX"
  echo "Elenco dischi:"
  lsblk -d -o NAME,SIZE,MODEL,TRAN 2>/dev/null || lsblk
  exit 1
fi

[ -f "$ISO" ] || { echo "ISO mancante: $ISO — esegui build-iso.sh"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Esegui con sudo"; exit 1; }

# Rifiuta se sembra disco di sistema
if [[ "$DEV" =~ nvme0n1$ ]] || [[ "$DEV" =~ sda$ ]]; then
  echo "ATTENZIONE: $DEV sembra disco primario. Usa --force solo se sei sicuro."
  if [ "${2:-}" != "--force" ]; then
    exit 1
  fi
fi

echo "ISO: $ISO"
echo "DEV: $DEV"
lsblk "$DEV" || true
echo ""
echo "Questo CANCELLA tutti i dati su $DEV"
read -r -p "Digita WRITE per continuare: " CONFIRM
[ "$CONFIRM" = "WRITE" ] || { echo "Annullato"; exit 1; }

umount "${DEV}"* 2>/dev/null || true
dd if="$ISO" of="$DEV" bs=4M status=progress conv=fsync
sync
echo "OK: USB scritta. Puoi bootare dalla chiavetta."
