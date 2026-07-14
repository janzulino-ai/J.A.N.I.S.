# win-vm

Vedi `infra/win-vm/README.md` per setup KVM.

## Brain

| Route | Ruolo |
|-------|--------|
| `/windows` | noVNC nel browser |
| `/ws/vnc` | Proxy WebSocket → VNC :5900 |
| `/api/win-vm/status` | Stato virsh |
| `/api/win-vm/start` | Avvia VM |
| `/api/win-vm/stop` | Stop VM |

## Env

```env
WIN_VM_NAME=win-vm
WIN_VM_VNC_HOST=127.0.0.1
WIN_VM_VNC_PORT=5900
WIN_VM_VNC_PASS=winvm01
```

## Setup server (sudo)

```bash
sudo bash infra/win-vm/run-pending-setup.sh
```
