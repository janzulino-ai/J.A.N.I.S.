# JANIS — Inventario dispositivi e piano deploy

> Coordinatore: **windows-pc** (Mode A) · brain `http://192.168.1.73:8001` · fleet fase 1

## Hub (Mode A — attivo)

| node_id | Dispositivo | Ruolo | Rete |
|---------|-------------|-------|------|
| **windows-pc** | MSI MS-7D08 · i9-11900K · RTX 3080 Ti · 16 GB | Brain WSL · Ollama Windows · UI Cursor | `192.168.1.73` · brain `:8001` |

## Hub (Mode B — rinviato)

| node_id | Dispositivo | Ruolo | Rete |
|---------|-------------|-------|------|
| **linux-server** | Samsung 970 EVO Plus · Debian 12 | Brain nativo · sidecar · kiosk HDMI | `192.168.1.72` · SSH `:22` |

## Satelliti / worker

| node_id | Dispositivo | OS | Ruolo | Rete |
|---------|-------------|-----|-------|------|
| **windows-pc** | MSI MS-7D08 · i9-11900K · RTX 3080 Ti · 16 GB | Windows 11 | Coordinator (Mode A) · dev Cursor/WSL | `192.168.1.73` |
| **mac-node** | Mac Mini M4 · 256 GB + SSD 512 GB USB-C | macOS | Worker fleet · bridge WS · SSH | `192.168.1.74` · `mac-mini-di-janzu.local` |
| **win-vm** | Windows guest KVM | Windows 11 | Worker · HDMI RTX · disco fisico | `127.0.0.1` sul server |
| **zenbook** | ASUS Zenbook · Core Ultra 9 185H · 32 GB · 1 TB | Windows 11 Home | Worker mobile · dev portatile · NPU | LAN / VPN |

## Mobile · JANIS Pocket

| node_id | Dispositivo | App | Ruolo | Rete |
|---------|-------------|-----|-------|------|
| **iphone-15-pro-max** | iPhone 15 Pro Max · A17 Pro · 6.7" | JANIS Pocket v3.1 | Corpo iOS · organi · push | LAN / WireGuard |
| **iphone-14-pro** | iPhone 14 Pro · A16 · 6.1" | JANIS Pocket v3.1 | Corpo iOS secondario | LAN / WireGuard |
| **ipad-pro-2020** | iPad Pro 12.9" (4ª gen, 2020) · A12Z · LiDAR | JANIS Pocket v3.1 | Tablet · presenza · HUD mobile | LAN / WireGuard |

Legacy ID (deprecati): `pocket-iphone`, `pocket-ipad` → sostituiti dagli ID sopra.

## Sidecar (sul hub, non nodi fleet)

Ollama · Glances `:61208` · LiteLLM · Qdrant `:6333` · STT · scheduler · autonomy

## VPN privata (accesso esterno)

WireGuard sul **windows-pc / WSL** (non porta 8001 su WAN):

| Parametro | Valore |
|-----------|--------|
| Hub LAN | `192.168.1.73` |
| Subnet tunnel | `10.8.0.0/24` |
| Server tunnel | `10.8.0.1` |
| Porta UDP | `51820` |
| Route client | `192.168.1.0/24` (LAN casa via tunnel) |
| Peer mobile | iPhone 15 PM · iPhone 14 Pro · iPad Pro · Zenbook |

Dopo VPN: stesso URL brain `http://192.168.1.73:8001` da tutti i client Pocket.

Setup: `infra/wsl/setup-wireguard.sh` · `infra/windows/install-wireguard-bridge.ps1` · template Pocket: `apps/pocket/docs/WIREGUARD-VPN-SETUP.md` · checklist: `docs/MOBILE-OPS.md`

## Piano install

### Sprint WSL — priorità (deadline API Cursor ~18 lug 2026)

| Fase | Contenuto | Stato |
|------|-----------|-------|
| **W0** | `setup-wsl-brain.sh` · Ollama GPU · venv · `.env` local-only | **done** |
| **W1** | Brain `:8001` · disabilita `cursor_code` · smoke chat Ollama | **done** |
| **W2** | Tool operativi: terminal · file · memoria · reflect · HUD chat/term · autofix | **done** |
| **W3** | HUD live hudcli08 · App Windows WPF · Cursor bridge `/api/cursor` | **done** |
| **W4** | Autostart WSL · tray Windows · smoke W2 · verify Mode A (`verify-mode-a.sh`) | **done** |
| **W5** | **LLM Auditor** · `POST /api/lab/audit` · judge · prompt/Modelfile output · `smoke-audit.sh` | **done** |
| **W5+** | Judge cloud · auto-fetch student · eval auto in promote cycle | **planned** |

Setup: `infra/wsl/README.md` · `scripts/setup-wsl-brain.sh` · **App Windows:** `apps/janis-windows/` (Visual Studio)

### Dual-mode

| Modalità | Descrizione | Stato |
|----------|-------------|-------|
| **A · WSL + Windows** | Brain WSL · Ollama Windows · app desktop · HUD · sidecar capability | **attiva** — install: [`SIDECARS-INSTALL.md`](SIDECARS-INSTALL.md) |
| **B · Debian SSD2** | Brain nativo · Ollama locale · i3/bspwm · kiosk HDMI | **ISO/USB ready · disk install gated** |

Canvas piano: `canvases/janis-dual-mode-plan.canvas.tsx`  
Gate wipe SSD2: [`MODE-B-SSD2-GATE.md`](MODE-B-SSD2-GATE.md) · TESTER: [`TESTER/README.md`](../TESTER/README.md)

### Debian nativo — fasi

| Fase | Contenuto | Stato |
|------|-----------|-------|
| **P0** | Debian 12 netinst · SSD2 LVM · NVIDIA X11 | **gated** (conferma utente) |
| **P1a** | i3 + i3status + rofi + Alacritty + lightdm | in rootfs `packages.list` |
| **P1b** | bspwm + sxhkd + polybar (upgrade) | deferred |
| **P2** | `install-server.sh` · systemd user nativo | ready post-OS |
| **P3** | HUD WS1 · Chromium kiosk | deferred |
| **P4** | GRUB HyperFluent · dual boot | tema minimo in `infra/grub/theme/` |
| **P5** | SSH + mount SSD2 condiviso | deferred |
| **P6** | WireGuard · accesso esterno | **Mode A: WSL hub** · Mode B deferred |
| **P7** | TESTER USB boot | **scripts ready** (`build-iso.sh` + `write-usb.sh`) |

## Dati condivisi (SSD2)

| Path | Contenuto |
|------|-----------|
| `/home/janis/projects/J.A.N.I.S.` | Monorepo git |
| `packages/brain/data/` | Chat · memoria · hardware · fleet state |
| `~/.ollama/models/` | Modelli LLM |
| `/home/janis/logs/sidecars/` | Log sidecar |

## Registro file

- `infra/fleet.yaml` — nodi fleet
- `packages/brain/data/hardware.json` — scheda tecnica per nodo
- `docs/ARCHITECTURE.md` — overview architettura
