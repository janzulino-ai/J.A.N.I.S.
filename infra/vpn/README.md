# WireGuard VPN — accesso esterno JANIS

Tunnel privato verso la LAN casa. Il brain resta su `192.168.1.72:8001` — **non** esporre quella porta su Internet.

## Architettura

```
[iPhone / iPad / Zenbook fuori casa]
        │ UDP 51820
        ▼
[linux-server wg0 · 10.8.0.1]
        │ route 192.168.1.0/24
        ▼
[brain :8001 · fleet WS · SSH]
```

## Install (sul server, dopo P2)

```bash
sudo apt install -y wireguard wireguard-tools
sudo bash infra/vpn/setup-wireguard.sh
```

Lo script genera chiavi in `/etc/wireguard/` e template peer in `infra/vpn/peers/` (gitignored).

## Peer previsti

| node_id | IP tunnel | Note |
|---------|-----------|------|
| iphone-15-pro-max | 10.8.0.10/32 | Pocket primary |
| iphone-14-pro | 10.8.0.11/32 | Pocket secondario |
| ipad-pro-2020 | 10.8.0.12/32 | Tablet |
| zenbook | 10.8.0.20/32 | Laptop Windows |

## Client iOS

Vedi `apps/pocket/docs/WIREGUARD-VPN-SETUP.md` — stesso URL LAN dopo connessione VPN.

## Firewall

```bash
# Solo WireGuard da WAN
sudo ufw allow 51820/udp
# NON: ufw allow 8001
```

## DDNS

Se IP pubblico dinamico: aggiorna `Endpoint` nei profili client (No-IP, DuckDNS, ecc.).

## Test

1. Wi‑Fi OFF su iPhone · VPN ON
2. `curl http://192.168.1.72:8001/api/status`
3. Pocket → Impostazioni → test connessione
