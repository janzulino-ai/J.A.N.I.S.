#!/usr/bin/env bash
# GPU ibrida: iGPU daily / RTX gaming (Phase B — richiede IOMMU + reboot)
set -euo pipefail

MODE="${1:-check}"
IGPU_PCI="${IGPU_PCI:-0000:00:02.0}"
RTX_PCI="${RTX_PCI:-0000:01:00.0}"

case "$MODE" in
  check)
    echo "=== GPU ==="
    lspci | grep -iE 'vga|3d|display' || true
    echo "=== IOMMU ==="
    dmesg 2>/dev/null | grep -i iommu | tail -3 || true
    grep -E 'iommu|intel_iommu|amd_iommu' /etc/default/grub 2>/dev/null || true
    ;;
  iommu)
    echo "Aggiungi a GRUB: intel_iommu=on iommu=pt"
    echo "Poi: sudo update-grub && sudo reboot"
    ;;
  desktop)
    echo "Phase B: bind iGPU ${IGPU_PCI} a host — implementare vfio bind"
    ;;
  gaming)
    echo "Phase B: passthrough RTX ${RTX_PCI} a win-vm — implementare vfio"
    ;;
  restore)
    echo "Ripristina QXL/VNC (Phase A)"
    ;;
  *)
    echo "Uso: $0 {check|iommu|desktop|gaming|restore}"
    exit 1
    ;;
esac
