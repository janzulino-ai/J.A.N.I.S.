#!/usr/bin/env bash
# Fix VNC: vga + password (TigerVNC / noVNC)
set -euo pipefail

WIN_VM_NAME="${WIN_VM_NAME:-win-vm}"
VNC_PASS="${VNC_PASS:-winvm01}"

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "Esegui con sudo"
  exit 1
fi

TMP=$(mktemp)
virsh dumpxml "$WIN_VM_NAME" > "$TMP"

python3 <<PY
import xml.etree.ElementTree as ET
import os
path = "$TMP"
tree = ET.parse(path)
root = tree.getroot()
devices = root.find("devices")
for g in devices.findall("graphics"):
    if g.get("type") == "vnc":
        g.set("passwd", os.environ.get("VNC_PASS", "winvm01"))
        g.set("listen", "127.0.0.1")
for v in devices.findall("video"):
    m = v.find("model")
    if m is not None:
        m.set("type", "vga")
        for a in ("ram", "vram", "heads"):
            if a in m.attrib:
                del m.attrib[a]
tree.write(path, encoding="unicode", xml_declaration=True)
PY

virsh destroy "$WIN_VM_NAME" 2>/dev/null || true
virsh define "$TMP"
virsh start "$WIN_VM_NAME"
rm -f "$TMP"
echo "VNC fix applicato (vga, passwd=${VNC_PASS})"
