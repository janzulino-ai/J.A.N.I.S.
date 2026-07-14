# Supporto server — task che richiedono accesso fisico o sudo

> Server brain: `janis@192.168.1.72` · path: `~/projects/J.A.N.I.S.`

## Una tantum (sudo)

Esegui **sul server** (SSH o tastiera locale):

```bash
# 1. Servizi user attivi dopo reboot (senza login)
sudo loginctl enable-linger janis
loginctl show-user janis -p Linger   # → Linger=yes

# 2. Kiosk pywebview (HUD senza barra Firefox)
sudo apt update
sudo apt install -y gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-gi firefox chromium-browser xorg xinit

# 3. win-vm KVM + Windows guest
cd ~/projects/J.A.N.I.S.
sudo bash infra/win-vm/run-pending-setup.sh

# 4. (Opzionale) Docker per Qdrant alternativo
sudo apt install -y docker.io
sudo usermod -aG docker janis
# logout/login poi: systemctl --user restart janis-qdrant
```

## Dopo ogni deploy da Mac

```bash
# Sul Mac
bash scripts/deploy-server.sh
```

Oppure manualmente sul server:

```bash
cd ~/projects/J.A.N.I.S.
git pull
bash infra/sidecars/setup-systemd-user.sh
systemctl --user restart janis
```

## Verifica servizi (no sudo)

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user is-active janis janis-glances janis-litellm janis-qdrant
curl -s http://127.0.0.1:8001/api/status | head -c 200
curl -s http://127.0.0.1:8001/api/host/inventory?refresh=true
curl -s -X POST http://127.0.0.1:8001/api/scout/discover -H 'Content-Type: application/json' -d '{}'
```

## Kiosk HDMI (tty1)

- Login console **tty1** → avvio automatico HUD `/server`
- Log: `~/.janis-kiosk.log`
- Se schermo nero: verificare `janis` active su :8001, poi `startx` manuale

## GRUB tema HyperFluent (fase avanzata)

Richiede sudo + reboot:

```bash
# Da implementare — vedi infra/grub/README.md
sudo cp -r infra/grub/theme /boot/grub/themes/janis
sudo update-grub
```

## TESTER USB installer

Build **da Mac o server Linux** (non da Windows):

```bash
cd TESTER
bash build-usb.sh    # crea immagine su chiavetta
```

## Quando chiedere supporto

| Sintomo | Azione supporto |
|---------|-----------------|
| `Linger=no` | `sudo loginctl enable-linger janis` |
| janis restart loop porta 8001 | `crontab -r`; `pkill -f run.py`; `systemctl --user restart janis` |
| Glances OFF | `systemctl --user restart janis-glances` |
| Qdrant OFF | `systemctl --user restart janis-qdrant`; log `journalctl --user -u janis-qdrant` |
| Kiosk senza fullscreen GTK | sudo apt pacchetti sopra |
| win-vm assente | sudo `run-pending-setup.sh` |
| GPU non vista | driver NVIDIA + `nvidia-smi` |

## Contatti / accesso

- SSH: `ssh janis` (chiave `~/.ssh/id_ed25519_jcrm`)
- HUD LAN: `http://192.168.1.72:8001/server`
- API: `http://192.168.1.72:8001/api/status`
