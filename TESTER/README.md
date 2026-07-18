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

**Importante (WSL):** `debootstrap` **non** può scrivere su `C:\` / `/mnt/c` (NTFS) — compare `tar failed`.  
La build usa `~/janis-iso-build` (ext4 Linux); l’ISO finale viene copiata in `C:\APP IA\JANIS\`.

### Windows (consigliato) — uno script

In PowerShell, **solo** queste righe (non incollare messaggi di errore):

```powershell
cd "C:\APP IA\JANIS"
git fetch origin
git checkout origin/cursor/cloud-agent-1784293795270-xoork -- TESTER/
powershell -ExecutionPolicy Bypass -File .\TESTER\build-iso-wsl.ps1
```

`git checkout ... -- TESTER/` serve tutti gli script (`install-packages.sh`, `config/packages.list`, ecc.).  
Non fare checkout solo di singoli file `.sh`.

Oppure da WSL (se sei gia' nel terminale Ubuntu, prompt `user@host:~$`):

```bash
bash "/mnt/c/APP IA/JANIS/TESTER/build-iso-wsl.sh"
```

**Non** digitare `wsl` dentro Ubuntu — quel comando esiste solo in PowerShell Windows.

Da PowerShell Windows:

```powershell
wsl -d Ubuntu --cd "C:\APP IA\JANIS" bash TESTER/build-iso-wsl.sh
```

Output:
- `C:\APP IA\JANIS\janis-tester.iso`
- `C:\APP IA\JANIS\TESTER\out\janis-tester.iso`

Se chiede password: digita quella dell’utente Ubuntu WSL. Prima: `wsl -d Ubuntu` → `sudo -v`.

### WSL / Linux — manuale (filesystem nativo)

```bash
export BUILD="$HOME/janis-iso-build/TESTER/build"
export ROOTFS="$BUILD/rootfs"
export OUT_DIR="$HOME/janis-iso-build/TESTER/out"
sudo apt install -y debootstrap debian-archive-keyring xorriso squashfs-tools \
  grub-pc-bin grub-efi-amd64-bin mtools dosfstools
cd "/mnt/c/APP IA/JANIS/TESTER"   # o path Linux del repo
sudo env BUILD="$BUILD" ROOTFS="$ROOTFS" BUILD_FORCE=1 bash build-base.sh
sudo env ROOTFS="$ROOTFS" bash verify-rootfs.sh
sudo env BUILD="$BUILD" ROOTFS="$ROOTFS" OUT_DIR="$OUT_DIR" bash build-iso.sh
cp -f "$OUT_DIR/janis-tester.iso" "../janis-tester.iso"
```

Se vedi `E: Tried to extract package, but tar failed`: stavi buildando su `/mnt/c` — usa `build-iso-wsl.sh`.

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
