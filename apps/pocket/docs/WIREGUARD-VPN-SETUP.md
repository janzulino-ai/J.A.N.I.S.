# WireGuard VPN — JANIS Pocket fuori casa (Mode A)

## Obiettivo

Raggiungere `http://192.168.1.73:8001` da **iPhone 15 Pro Max**, **iPhone 14 Pro** e **iPad Pro 2020** fuori casa, più **Zenbook** Windows, senza esporre JANIS su Internet.

Server VPN: **windows-pc / WSL** (`infra/wsl/setup-wireguard.sh`).

## Peer fleet

| node_id | IP tunnel | Dispositivo |
|---------|-----------|-------------|
| iphone-15-pro-max | 10.8.0.10 | iPhone 15 Pro Max |
| iphone-14-pro | 10.8.0.11 | iPhone 14 Pro |
| ipad-pro-2020 | 10.8.0.12 | iPad Pro 12.9" 4ª gen 2020 |
| zenbook | 10.8.0.20 | ASUS Zenbook |

## Server (windows-pc · WSL)

1. `sudo bash infra/wsl/setup-wireguard.sh`
2. Windows Admin: `infra/windows/setup-wireguard-forward.ps1`
3. Porta UDP: **51820**
4. Subnet: `10.8.0.0/24`
5. Route LAN: `192.168.1.0/24`
6. Config client in `infra/vpn/peers/<node_id>/client.conf`

## iPhone / iPad (client)

1. Installa [WireGuard](https://apps.apple.com/app/wireguard/id1441195209)
2. JANIS Pocket → Impostazioni → **VPN WireGuard** → copia template (o incolla `client.conf`)
3. WireGuard → Aggiungi tunnel → Attiva

Pocket rileva automaticamente `device_id`: `iphone-15-pro-max`, `iphone-14-pro`, `ipad-pro-2020`.

## JANIS Pocket

1. **URL LAN**: `http://192.168.1.73:8001`
2. **URL VPN**: stesso valore (dopo tunnel la LAN è raggiungibile)
3. Toggle **Usa server VPN** quando sei fuori casa
4. Token `X-JANIS-Token` se configurato sul brain

## Template config (es. iPhone 14 Pro)

Vedi `infra/vpn/peers/iphone-14-pro/client.conf.example`:

```ini
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
Address = 10.8.0.11/32
DNS = 192.168.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <TUO_DDNS_O_IP>:51820
AllowedIPs = 192.168.1.0/24
PersistentKeepalive = 25
```

## Sicurezza

- Non aprire porta 8001 su WAN
- Solo UDP 51820 (WireGuard) verso router → `192.168.1.73`
- Usa DDNS se IP dinamico
- Token obbligatorio per hub in produzione

## Test

1. Wi‑Fi OFF, VPN ON
2. Safari → `http://192.168.1.73:8001/api/status`
3. Pocket → Salva e testa → **Online**
4. Verifica presenza con `device_id` corretto in `/api/presence`

Checklist completa: `docs/MOBILE-OPS.md`
