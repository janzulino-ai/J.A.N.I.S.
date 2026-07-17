# GRUB tema JANIS (Live Distro)

## Obiettivo

Portale di boot **grafico e statico** (HUD dark).  
L’animazione neuroni **non** gira in GRUB — parte dopo il kernel in kiosk (`/server?phase=boot`).  
Spec prodotto: [`docs/LIVE-DISTRO.md`](../../docs/LIVE-DISTRO.md) · canvas: `canvases/janis-live-distro.canvas.tsx`.

**`theme/background.png` = master background del sistema Live Distro**  
(GRUB → splash neuroni → wizard → HUD). Stessa base ovunque; solo layer sopra, non un altro tema.

**Menu = finestra sovrapposta** allo sfondo (come i panel del wizard):  
`theme.txt` → `boot_menu` a destra (~52%/22%/40%/56%); cornice vetro/cyan disegnata nel PNG.  
Non usare menu full-bleed.

## Requisiti server / build ISO

```bash
sudo apt install grub2-common grub-pc-bin grub-efi-amd64-bin
```

Usato da [`TESTER/build-iso.sh`](../../TESTER/build-iso.sh) (copia `theme/` nell’ISO).

## Checklist asset (statici)

| File | Stato | Spec |
|------|-------|------|
| `theme/theme.txt` | presente | `boot_menu` finestra overlay (non full-bleed), Unifont |
| `theme/background.png` | placeholder + **pannello menu** a destra | 1920×1080 master · griglia · cornice overlay allineata a `boot_menu` |
| `theme/selected_c.png` | placeholder | barra selezione ~720×32 dentro la finestra |
| `backgrounds/janis.png` | opzionale | variante brand |
| `backgrounds/linux.png` | opzionale | HyperFluent focus voce menu |

Stile riferimento: Adobe Stock “futuristic HUD” + [`packages/brain/frontend/janis-theme.css`](../../packages/brain/frontend/janis-theme.css).  
PNG 8-bit o 24-bit; evitare alpha esotica se GRUB host è picky.

### Produzione rapida (placeholder)

Finché manca un PNG artistico, `build-iso.sh` crea un file vuoto — **sostituire** prima del release Live Distro con asset reale nella checklist sopra.

## Menu ISO (Live Distro)

Voci consigliate (allineare `TESTER/build-iso.sh` quando si chiude live-boot):

1. **JANIS Safe Live** — no NVIDIA  
2. **JANIS Chat-ready** — brain + Ollama (profilo ISO #2)  
3. **JANIS NVIDIA Live** — solo su ISO #3  
4. **Info install / SSD gate** — testo MODE-B, no wipe  
5. **Boot next disk**

## Installazione su sistema installato (post-SSD)

```bash
sudo mkdir -p /boot/grub/themes/janis
sudo cp -r infra/grub/theme/* /boot/grub/themes/janis/
# /etc/default/grub → GRUB_THEME=/boot/grub/themes/janis/theme.txt
sudo update-grub && sudo reboot
```

## Post-boot (non GRUB)

| Step | Azione |
|------|--------|
| splash neuroni | Chromium kiosk → `http://127.0.0.1:8001/server?phase=boot` |
| codice | `janis-neurons.js` / `JanisBrain` |
| poi | wizard setup (`docs/LIVE-DISTRO.md` § Setup wizard) |

## Riferimento HUD Windows Terminal palette

Stile infografico legacy: `packages/kiosk/static/server-infographic.css` (palette).  
Live Distro UI runtime preferisce `janis-theme.css` sci-fi.
