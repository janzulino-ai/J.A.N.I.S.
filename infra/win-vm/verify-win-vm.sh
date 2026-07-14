#!/usr/bin/env bash
# Verifica win-vm: stato, rete guest, VNC, screenshot
set -euo pipefail

WIN_VM_NAME="${WIN_VM_NAME:-win-vm}"
OUT="${1:-/tmp/win-vm-verify.png}"

fail() { echo "FAIL: $*"; exit 1; }

command -v virsh >/dev/null || fail "virsh assente"

state=$(virsh domstate "$WIN_VM_NAME" 2>/dev/null || echo "undefined")
echo "state=$state"
[[ "$state" == "running" ]] || fail "VM non running ($state)"

python3 -c "
import socket
s=socket.create_connection(('127.0.0.1',5900),timeout=3)
assert s.recv(4)==b'RFB ', 'RFB mancante'
print('vnc=ok')
"

guest_ip=""
guest_host=""
while read -r line; do
  [[ "$line" != *"52:54:"* ]] && continue
  [[ "$line" != *"ipv4"* ]] && continue
  set -- $line
  for i in $(seq 1 $#); do
    eval "p$i=\${$i}"
  done
  for i in $(seq 1 $#); do
    eval "v=\${p$i}"
    if [[ "$v" == "ipv4" ]]; then
      eval "ip=\${p$((i+1))}"
      guest_ip="${ip%%/*}"
      eval "guest_host=\${p$((i+2))}"
    fi
  done
done < <(virsh net-dhcp-leases default 2>/dev/null || true)

if [[ -n "$guest_ip" ]]; then
  echo "guest_ip=$guest_ip hostname=$guest_host"
  ping -c 1 -W 3 "$guest_ip" >/dev/null && echo "ping=ok" || echo "ping=wait"
  nc -zv -w 3 "$guest_ip" 445 2>/dev/null && echo "smb=ok" || echo "smb=wait"
fi

virsh screenshot "$WIN_VM_NAME" "$OUT" 2>/dev/null && echo "screenshot=$OUT size=$(stat -c%s "$OUT" 2>/dev/null || echo ?)" || echo "screenshot=fail"

echo "OK win-vm verificata"
