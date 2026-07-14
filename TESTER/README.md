# TESTER — USB/ISO installazione JANIS base

Installer avviabile per macchina destinazione.

## Flusso target

1. Boot GRUB (tema JANIS) + scan hardware + barra progresso
2. Scelta: **Installa come server** (SSD dedicato) | **Installa su WSL** (post-avvio)
3. Fetch risorse OSS + download con progresso + terminale
4. Funzioni successive in base alla scelta

## Build (server Linux consigliato)

```bash
# Sul server 192.168.1.72
sudo apt install -y debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin
cd TESTER
sudo bash build-base.sh              # rootfs in build/rootfs
sudo bash build-iso.sh               # out/janis-tester.iso
sudo bash write-usb.sh /dev/sdX      # ATTENZIONE: sostituire sdX con chiavetta
```

## Build da Mac (solo scrittura USB)

```bash
# Dopo rsync ISO dal server:
sudo dd if=out/janis-tester.iso of=/dev/rdiskX bs=4m status=progress
```

## Stato implementazione

| Componente | Stato |
|------------|--------|
| debootstrap base | script `build-base.sh` |
| GRUB + tema | `infra/grub/` + TODO gfxmenu |
| Scan HW boot | TODO initramfs hook |
| Installer UI | TODO Python/Textual |
| Server install | TODO → brain + sidecars |
| WSL path | TODO post-boot |

## File

- `build-base.sh` — debootstrap minimal
- `build-iso.sh` — xorriso hybrid ISO
- `write-usb.sh` — dd con conferma
- `config/packages.list` — pacchetti base
