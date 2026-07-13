# WireGuard VPN — JANICE Pocket fuori casa

## Obiettivo

Raggiungere `http://192.168.1.72:8001` dall'iPhone **fuori casa** tramite tunnel WireGuard sul router, senza esporre JANIS su Internet.

## Router (server WireGuard)

1. Abilita WireGuard sul router (es. Fritz!Box, OpenWrt, pfSense).
2. Rete tunnel suggerita: `10.8.0.0/24`
3. Server IP tunnel: `10.8.0.1`
4. Porta UDP: **51820**
5. `AllowedIPs` peer iPhone: `10.8.0.2/32`
6. Route verso LAN casa: `192.168.1.0/24` raggiungibile dal tunnel

Genera chiavi:
```bash
wg genkey | tee client.key | wg pubkey > client.pub
```

## iPhone (client)

1. Installa [WireGuard](https://apps.apple.com/app/wireguard/id1441195209)
2. JANICE Pocket → Impostazioni → **VPN WireGuard** → copia template config
3. WireGuard → Aggiungi tunnel → Incolla config
4. Attiva tunnel

## JANICE Pocket

1. **URL LAN**: `http://192.168.1.72:8001` (invariato)
2. **URL VPN**: stesso valore (dopo tunnel la LAN è raggiungibile)
3. Toggle **Usa server VPN** quando sei fuori casa
4. Token `X-JANIS-Token` se configurato sul brain

## Template config

```ini
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
Address = 10.8.0.2/32
DNS = 192.168.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <TUO_DDNS_O_IP>:51820
AllowedIPs = 192.168.1.0/24
PersistentKeepalive = 25
```

## Sicurezza

- Non aprire porta 8001 su WAN
- Solo UDP 51820 (WireGuard) verso router
- Usa DDNS se IP dinamico
- Token obbligatorio per hub esposto

## Test

1. Wi‑Fi OFF, VPN ON
2. Safari → `http://192.168.1.72:8001/api/status` (opzionale)
3. Pocket → Impostazioni → Salva e testa → **Online**
4. Chat + telemetry + bridge attivi
