#!/usr/bin/env bash
# Setup completo win-vm (richiede sudo)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "Esegui: sudo bash infra/win-vm/run-pending-setup.sh"
  exit 1
fi

# shellcheck source=/dev/null
[[ -f "$ROOT/win-vm.env" ]] && source "$ROOT/win-vm.env"

bash "$ROOT/detect-win-disk.sh"
WIN_DISK="${WIN_DISK:-/dev/nvme1n1}"
VNC_PASS="${VNC_PASS:-winvm01}"

vm_disk=$(virsh dumpxml win-vm 2>/dev/null | grep -oP "source dev='\K[^']+" | head -1 || true)
if [[ "${vm_disk}" != "${WIN_DISK}" ]]; then
  echo "==> [1/3] Ricrea win-vm su ${WIN_DISK}"
  WIN_DISK="${WIN_DISK}" bash "$ROOT/create-win-vm-phase-a.sh"
else
  echo "==> [1/3] win-vm già su ${WIN_DISK} — skip"
fi

echo "==> [2/3] Fix VNC"
VNC_PASS="${VNC_PASS}" bash "$ROOT/fix-win-vm-vnc.sh"

echo "==> [3/3] Inventario Windows"
bash "$ROOT/setup-windows-inventory.sh" || true

echo "Fatto. Mac: ssh -N -L 5901:127.0.0.1:5900 janis → TigerVNC localhost:5901"
echo "Browser: http://SERVER:8001/windows"
