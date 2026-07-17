# GRUB tema HyperFluent — JANIS

## Obiettivo

Sfondo dinamico al cursore: janis / linux / windows / apple (`backgrounds/<classe>.png`).

## Requisiti server

```bash
sudo apt install grub2-common grub-pc-bin
# Patch opzionale: grub-gfxmenu-bg-mod
```

## Installazione (TODO)

1. Copiare `theme/` in `/boot/grub/themes/janis/`
2. `/etc/default/grub`: `GRUB_THEME=/boot/grub/themes/janis/theme.txt`
3. `sudo update-grub && sudo reboot`

## Asset

- `theme/theme.txt` — tema minimo usato da `TESTER/build-iso.sh`
- `backgrounds/janis.png` — default (opzionale HyperFluent)
- `backgrounds/linux.png`, `windows.png`, `apple.png` — al focus voce menu

## Riferimento

Stile HUD HyperFluent in `packages/kiosk/static/server-infographic.css`
