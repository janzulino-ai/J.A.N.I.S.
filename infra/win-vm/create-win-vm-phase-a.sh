#!/usr/bin/env bash
# Fase A: win-vm su disco Windows fisico (KVM, QXL/VNC, e1000e)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$ROOT/win-vm.env" ]] && source "$ROOT/win-vm.env"

WIN_VM_NAME="${WIN_VM_NAME:-win-vm}"
WIN_DISK="${WIN_DISK:-}"
VM_RAM_MB="${VM_RAM_MB:-32768}"
VM_VCPUS="${VM_VCPUS:-8}"
VNC_PORT="${VNC_PORT:-5900}"
VNC_PASS="${VNC_PASS:-winvm01}"

if [[ -z "$WIN_DISK" ]]; then
  eval "$("$ROOT/detect-win-disk.sh" 2>/dev/null | grep '^WIN_DISK=')" || true
fi
if [[ -z "$WIN_DISK" || ! -b "$WIN_DISK" ]]; then
  echo "WIN_DISK non trovato. Esegui: bash detect-win-disk.sh"
  exit 1
fi

ROOT_DEV="$(findmnt -n -o SOURCE / | sed 's/p[0-9]*$//' | sed 's/[0-9]*$//' || true)"
if [[ "$WIN_DISK" == "$ROOT_DEV" ]] || [[ "/dev/$(lsblk -no PKNAME "$ROOT_DEV" 2>/dev/null)" == "$WIN_DISK" ]]; then
  echo "ERRORE: WIN_DISK=$WIN_DISK coincide con disco Ubuntu — abort."
  exit 1
fi

if ! command -v virsh >/dev/null 2>&1; then
  echo "Installa: sudo apt install qemu-kvm libvirt-daemon-system virtinst"
  exit 1
fi

XML="/tmp/${WIN_VM_NAME}.xml"
cat > "$XML" <<EOF
<domain type='kvm'>
  <name>${WIN_VM_NAME}</name>
  <memory unit='MiB'>${VM_RAM_MB}</memory>
  <vcpu placement='static'>${VM_VCPUS}</vcpu>
  <os>
    <type arch='x86_64' machine='pc-q35-8.2'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-passthrough'/>
  <clock offset='localtime'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <disk type='block' device='disk'>
      <driver name='qemu' type='raw' cache='none' io='native'/>
      <source dev='${WIN_DISK}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='network'>
      <source network='default'/>
      <model type='e1000e'/>
    </interface>
    <graphics type='vnc' port='${VNC_PORT}' autoport='no' listen='127.0.0.1' passwd='${VNC_PASS}'/>
    <video>
      <model type='qxl' ram='65536' vram='65536' heads='1'/>
    </video>
    <console type='pty'/>
    <channel type='spicevmc'>
      <target type='virtio' name='com.redhat.spice.0'/>
    </channel>
  </devices>
</domain>
EOF

virsh destroy "$WIN_VM_NAME" 2>/dev/null || true
virsh undefine "$WIN_VM_NAME" 2>/dev/null || true
virsh define "$XML"
echo "Definita ${WIN_VM_NAME} su ${WIN_DISK}"
virsh start "$WIN_VM_NAME" || virsh autostart "$WIN_VM_NAME"
echo "Stato: $(virsh domstate "$WIN_VM_NAME" 2>/dev/null || echo unknown)"
