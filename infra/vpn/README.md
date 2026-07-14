# WireGuard VPN — accesso esterno JANIS (Mode A)

Tunnel privato verso la LAN casa. Il brain resta su **`192.168.1.73:8001`** (windows-pc / WSL) — **non** esporre quella porta su Internet.

> Mode B (linux-server `192.168.1.72`) è rinviato. Usa `infra/vpn/setup-wireguard.sh` sul server Debian quando attivo.

## Architettura (Mode A — attivo)

```
[iPhone / iPad / Zenbook fuori casa]
        │ UDP 51820 (router → Windows PC)
        ▼
[Windows PC 192.168.1.73 · firewall UDP 51820]
        ▼
[WSL wg0 · 10.8.0.1]
        │ route 192.168.1.0/24
        ▼
[brain WSL :8001 · fleet WS · HUD]
```

## Install rapido (windows-pc)

**PowerShell (Admin):**

```powershell
powershell -ExecutionPolicy Bypass -File "C:\APP IA\JANIS\infra\windows\install-wireguard-bridge.ps1"
```

**WSL (WireGuard server):**

```bash
sudo apt install -y wireguard wireguard-tools
sudo bash ~/projects/J.A.N.I.S./infra/wsl/setup-wireguard.sh
```

**Firewall Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File infra/windows/setup-wireguard-forward.ps1
```

## Peer previsti

| node_id | IP tunnel | Note |
|---------|-----------|------|
| iphone-15-pro-max | 10.8.0.10/32 | Pocket primary |
| iphone-14-pro | 10.8.0.11/32 | Pocket secondario |
| ipad-pro-2020 | 10.8.0.12/32 | Tablet |
| zenbook | 10.8.0.20/32 | Laptop Windows |

Template committati: `infra/vpn/peers/<node_id>/client.conf.example`  
Config reali (gitignored): `infra/vpn/peers/<node_id>/client.conf`

## Client iOS

Vedi `apps/pocket/docs/WIREGUARD-VPN-SETUP.md` — stesso URL LAN dopo connessione VPN.

## Router / WAN

1. Forward **UDP 51820** → `192.168.1.73` (Windows PC)
2. Imposta `WG_ENDPOINT=<IP_pubblico_o_DDNS>:51820` prima di distribuire i client
3. DDNS consigliato se IP dinamico (No-IP, DuckDNS, ecc.)

## WSL2 networking

Per UDP stabile, mirrored mode in `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
firewall=true
```

Poi `wsl --shutdown` e riavvia WireGuard.

## API brain

```bash
curl http://192.168.1.73:8001/api/vpn/status
```

## Test

1. Wi‑Fi OFF su iPhone · VPN ON
2. `curl http://192.168.1.73:8001/api/status`
3. Pocket → Impostazioni → test connessione

## Script legacy (linux-server)

`infra/vpn/setup-wireguard.sh` — identico peer map, per hub Debian futuro (Mode B).
