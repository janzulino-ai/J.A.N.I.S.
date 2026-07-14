#!/usr/bin/env bash
# Applica listen VNC 127.0.0.1 (senza password — noVNC via proxy brain)
set -euo pipefail

WIN_VM_NAME="${WIN_VM_NAME:-win-vm}"

if ! virsh dominfo "$WIN_VM_NAME" &>/dev/null; then
  exit 0
fi

TMP=$(mktemp)
export TMP
virsh dumpxml "$WIN_VM_NAME" > "$TMP"

python3 <<'PY'
import os
import xml.etree.ElementTree as ET

path = os.environ["TMP"]
tree = ET.parse(path)
root = tree.getroot()
devices = root.find("devices")
for g in devices.findall("graphics"):
    if g.get("type") == "vnc":
        g.attrib.pop("passwd", None)
        g.set("listen", "127.0.0.1")
        g.set("listen_type", "address")
        for listen in list(g.findall("listen")):
            g.remove(listen)
        listen = ET.SubElement(g, "listen")
        listen.set("type", "address")
        listen.set("address", "127.0.0.1")
tree.write(path, encoding="unicode", xml_declaration=True)
PY

WAS_RUNNING=$(virsh domstate "$WIN_VM_NAME" 2>/dev/null || echo "shut off")
virsh destroy "$WIN_VM_NAME" 2>/dev/null || true
virsh define "$TMP"
if [[ "$WAS_RUNNING" == "running" ]]; then
  virsh start "$WIN_VM_NAME"
fi
rm -f "$TMP"
echo "VNC listen 127.0.0.1 (no passwd)"
