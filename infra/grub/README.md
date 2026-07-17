# GRUB tema JANIS (Live Distro)

## Obiettivo

Portale di boot **grafico e statico** (HUD dark).  
L’animazione neuroni **non** gira in GRUB — parte dopo il kernel in kiosk (`/server?phase=boot`).  
Spec prodotto: [`docs/LIVE-DISTRO.md`](../../docs/LIVE-DISTRO.md) · canvas: `canvases/janis-live-distro.canvas.tsx`.

## Requisiti server / build ISO

```bash
sudo apt install grub2-common grub-pc-bin grub-efi-amd64-bin
```

Usato da [`TESTER/build-iso.sh`](../../TESTER/build-iso.sh) (copia `theme/` nell’ISO).

## Checklist asset (statici)

| File | Stato | Spec |
|------|-------|------|
| `theme/theme.txt` | presente | title JANIS, menu 15%/30%, Unifont |
| `theme/background.png` | **da produrre** | 1920×1080 · `#050B12` void · accent `#3DE0FF` · griglia HUD · wordmark J.A.N.I.S. · no testo menu nel PNG (il menu è GRUB) |
| `theme/selected_c.png` / `selected_*.png` | **da produrre** | barra selezione cyan sottile (altezza ~28px item) |
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
