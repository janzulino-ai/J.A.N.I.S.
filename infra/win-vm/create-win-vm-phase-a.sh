#!/usr/bin/env bash
# Profilo win-vm — disco fisico Windows UEFI (Secure Boot, SATA, QXL+VNC)
# Testato: boot lock screen Windows 11 su nvme0n1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[[ -f "$ROOT/win-vm.env" ]] && source "$ROOT/win-vm.env"

WIN_VM_NAME="${WIN_VM_NAME:-win-vm}"
WIN_DISK="${WIN_DISK:-}"
VM_RAM_MB="${VM_RAM_MB:-16384}"
VM_VCPUS="${VM_VCPUS:-4}"
VNC_PORT="${VNC_PORT:-5900}"
VNC_PASS="${VNC_PASS:-winvm01}"

if [[ -z "$WIN_DISK" ]]; then
  eval "$("$ROOT/detect-win-disk.sh" 2>/dev/null | grep '^WIN_DISK=')" || true
fi
if [[ -z "$WIN_DISK" || ! -b "$WIN_DISK" ]]; then
  echo "WIN_DISK non trovato"
  exit 1
fi

ROOT_DEV="$(findmnt -n -o SOURCE / | sed 's/p[0-9]*$//' | sed 's/[0-9]*$//' || true)"
if [[ "$WIN_DISK" == "$ROOT_DEV" ]] || [[ "/dev/$(lsblk -no PKNAME "$ROOT_DEV" 2>/dev/null)" == "$WIN_DISK" ]]; then
  echo "ERRORE: WIN_DISK=$WIN_DISK è il disco Ubuntu"
  exit 1
fi

if ! command -v virsh >/dev/null 2>&1; then
  echo "Installa: apt install qemu-system-x86 libvirt-daemon-system"
  exit 1
fi

XML="$(mktemp /tmp/${WIN_VM_NAME}.XXXXXX.xml)"
trap 'rm -f "$XML"' EXIT

cat > "$XML" <<EOF
<domain type='kvm'>
  <name>${WIN_VM_NAME}</name>
  <memory unit='MiB'>${VM_RAM_MB}</memory>
  <vcpu placement='static'>${VM_VCPUS}</vcpu>
  <os firmware='efi'>
    <type arch='x86_64' machine='pc-q35-8.2'>hvm</type>
    <firmware>
      <feature enabled='yes' name='enrolled-keys'/>
      <feature enabled='yes' name='secure-boot'/>
    </firmware>
    <loader readonly='yes' secure='yes' type='pflash' format='raw'>/usr/share/OVMF/OVMF_CODE_4M.ms.fd</loader>
    <nvram template='/usr/share/OVMF/OVMF_VARS_4M.ms.fd' templateFormat='raw' format='raw'>/var/lib/libvirt/qemu/nvram/${WIN_VM_NAME}_VARS.fd</nvram>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <hyperv mode='custom'>
      <relaxed state='on'/>
      <vapic state='on'/>
      <spinlocks state='on' retries='8191'/>
      <vpindex state='on'/>
      <runtime state='on'/>
      <synic state='on'/>
      <stimer state='on'/>
    </hyperv>
    <smm state='on'/>
  </features>
  <cpu mode='host-passthrough' check='none' migratable='on'/>
  <clock offset='localtime'>
    <timer name='rtc' tickpolicy='catchup'/>
    <timer name='hpet' present='no'/>
    <timer name='hypervclock' present='yes'/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <disk type='block' device='disk'>
      <driver name='qemu' type='raw' cache='none' io='native'/>
      <source dev='${WIN_DISK}'/>
      <target dev='sda' bus='sata'/>
    </disk>
    <controller type='sata' index='0'>
      <address type='pci' domain='0x0000' bus='0x00' slot='0x1f' function='0x2'/>
    </controller>
    <interface type='network'>
      <source network='default'/>
      <model type='e1000e'/>
    </interface>
    <graphics type='vnc' port='${VNC_PORT}' autoport='no' listen='127.0.0.1'>
      <listen type='address' address='127.0.0.1'/>
    </graphics>
    <video>
      <model type='qxl' ram='65536' vram='65536' heads='1'/>
    </video>
    <memballoon model='virtio'/>
    <input type='tablet' bus='usb'/>
    <input type='keyboard' bus='ps2'/>
    <channel type='unix'>
      <target type='virtio' name='org.qemu.guest_agent.0'/>
    </channel>
  </devices>
</domain>
EOF

virsh destroy "$WIN_VM_NAME" 2>/dev/null || true
virsh undefine "$WIN_VM_NAME" --nvram 2>/dev/null || virsh undefine "$WIN_VM_NAME" 2>/dev/null || true
virsh define "$XML"
virsh autostart "$WIN_VM_NAME"
echo "Definita ${WIN_VM_NAME} su ${WIN_DISK}"
virsh start "$WIN_VM_NAME"
echo "Stato: $(virsh domstate "$WIN_VM_NAME")"
