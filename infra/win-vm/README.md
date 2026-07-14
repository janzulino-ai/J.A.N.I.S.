# win-vm — Windows in KVM

Fase A (attuale): disco fisico Windows, VNC `127.0.0.1:5900`, no GPU passthrough.

## Setup (sul server, con sudo)

```bash
cd ~/projects/J.A.N.I.S.
sudo bash infra/win-vm/run-pending-setup.sh
```

## Rileva disco

```bash
bash infra/win-vm/detect-win-disk.sh
```

Copia `win-vm.env.example` → `win-vm.env` se serve override.

## Accesso

| Metodo | URL |
|--------|-----|
| noVNC browser | `http://192.168.1.72:8001/windows` |
| TigerVNC Mac | `ssh -N -L 5901:127.0.0.1:5900 janis` → `localhost:5901` |

## Phase B (futuro)

`setup-hybrid-gpu.sh` — IOMMU + passthrough RTX HDMI.
