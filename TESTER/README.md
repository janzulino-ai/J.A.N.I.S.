# TESTER — USB/ISO installazione JANIS base

Installer / rescue bootabile per macchina destinazione (Mode B).

**Live Distro (prodotto):** specifica completa in [`docs/LIVE-DISTRO.md`](../docs/LIVE-DISTRO.md) · canvas [`canvases/janis-live-distro.canvas.tsx`](../canvases/janis-live-distro.canvas.tsx).

| Hardware | Valore |
|----------|--------|
| RAM minimo | **16 GB** |
| RAM consigliati | **32 GB** |
| USB | **32 GB** per profilo (fino a 4 ISO: Safe / Chat-ready / NVIDIA / Media) |

## Flusso build (locale — non GitHub)

L’ISO **non** viene creata dal push git: va generata sul PC.

### Windows (consigliato) — uno script

```powershell
cd "C:\APP IA\JANIS\TESTER"
powershell -ExecutionPolicy Bypass -File .\build-iso-wsl.ps1
```

Output: `C:\APP IA\JANIS\TESTER\out\janis-tester.iso`

### WSL / Linux — manuale

```bash
sudo apt install -y debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools
cd TESTER
sudo BUILD_FORCE=1 bash build-base.sh   # debootstrap + packages.list + chroot-config
sudo bash verify-rootfs.sh
sudo bash build-iso.sh                  # out/janis-tester.iso
sudo bash write-usb.sh /dev/sdX         # digita WRITE — distruttivo per la chiavetta
```

Se `out/janis-tester.iso` manca: la build non è stata eseguita o è fallita a metà (guarda errori `debootstrap` / `sudo`).

## Script

| Script | Ruolo |
|--------|--------|
| `build-base.sh` | debootstrap → `install-packages.sh` → `chroot-config.sh` |
| `install-packages.sh` | legge `config/packages.list` |
| `chroot-config.sh` | utente janis, SSH, i3, first-boot NVIDIA |
| `verify-rootfs.sh` | check kernel/grub/i3/ssh |
| `build-iso.sh` | squashfs + GRUB + xorriso → `out/janis-tester.iso` |
| `write-usb.sh` | `dd` ISO → USB (conferma `WRITE`) |
| `deploy-disk.sh` | wipe disco + rsync rootfs (**non** in questo sprint senza OK) |

## Boot menu ISO

1. **Live/Rescue (try)** — kernel/initrd da rootfs se presenti  
2. **info install** — ricorda `deploy-disk.sh` / netinst  
3. **Boot next disk**

Target Live Distro (dopo `live-boot`): GRUB grafico statico → **neuron splash** kiosk → wizard chat/voce.  
Neuroni **non** in GRUB — vedi `docs/LIVE-DISTRO.md`.

UI Textual scenografica (risorse HUD + overlay) = wizard post-boot; ISO MVP bootabile non la richiede per il primo `build-iso.sh`.

## Mode B gate SSD2

**Non** eseguire `deploy-disk.sh` sul Samsung 970 EVO finché non confermi esplicitamente.  
MVP disk: Debian 12 netinst ufficiale → poi `scripts/install-server.sh`.  
Vedi [`docs/FLEET-DEVICES.md`](../docs/FLEET-DEVICES.md) e [`docs/MODE-B-SSD2-GATE.md`](../docs/MODE-B-SSD2-GATE.md).

## Build da Mac (solo scrittura)

Dopo aver copiato l’ISO dal host Linux:

```bash
sudo dd if=out/janis-tester.iso of=/dev/rdiskX bs=4m status=progress
```

## Stato

| Componente | Stato |
|------------|--------|
| debootstrap + packages.list | wired |
| chroot-config / first-boot | ok |
| GRUB theme minimo | `infra/grub/theme/` |
| ISO xorriso / grub-mkrescue | `build-iso.sh` |
| write-usb | `write-usb.sh` |
| Installer UI Textual | TODO follow-up |
| Wipe SSD2 | **gated** |
