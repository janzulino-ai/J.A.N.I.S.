# TESTER — USB/ISO installazione JANIS base

Installer / rescue bootabile per macchina destinazione (Mode B).

## Flusso build (Linux o WSL2 con sudo)

```bash
sudo apt install -y debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools
cd TESTER
sudo BUILD_FORCE=1 bash build-base.sh   # debootstrap + packages.list + chroot-config
sudo bash verify-rootfs.sh
sudo bash build-iso.sh                  # out/janis-tester.iso
sudo bash write-usb.sh /dev/sdX         # digita WRITE — distruttivo per la chiavetta
```

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

UI Textual completa (scan HW, progresso OSS) = follow-up; non richiesta per ISO bootabile MVP.

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
