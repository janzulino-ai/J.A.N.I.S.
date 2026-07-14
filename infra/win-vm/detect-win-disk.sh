#!/usr/bin/env bash
# Rileva disco/partizione Windows (label WIN o NTFS grande)
set -euo pipefail

echo "=== Block devices ==="
lsblk -o NAME,SIZE,LABEL,FSTYPE,MOUNTPOINT | grep -E 'NAME|nvme|WIN|NTFS' || true

WIN_DISK=""
WIN_PART=""

# Partizione con label WIN
while read -r name label fstype; do
  if [[ "${label}" == "WIN" ]] && [[ -b "/dev/${name}" ]]; then
    WIN_PART="/dev/${name}"
    disk="${name%%[0-9]*}"
    [[ -n "$disk" && "$disk" != "$name" ]] && WIN_DISK="/dev/${disk}"
    break
  fi
done < <(lsblk -rno NAME,LABEL,FSTYPE 2>/dev/null || true)

if [[ -z "$WIN_PART" ]]; then
  # Fallback: NTFS > 200G non montato
  while read -r name fstype size; do
    if [[ "$fstype" == "ntfs" ]] && [[ -b "/dev/${name}" ]]; then
      WIN_PART="/dev/${name}"
      disk="${name%%[0-9]*}"
      [[ -n "$disk" && "$disk" != "$name" ]] && WIN_DISK="/dev/${disk}"
      break
    fi
  done < <(lsblk -rno NAME,FSTYPE,SIZE 2>/dev/null | grep -i ntfs || true)
fi

echo ""
echo "WIN_DISK=${WIN_DISK:-unset}"
echo "WIN_PART=${WIN_PART:-unset}"
echo "Ubuntu root (non usare come VM disk): $(findmnt -n -o SOURCE / 2>/dev/null || echo '?')"
