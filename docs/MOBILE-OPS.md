# JANIS — checklist operativa mobile (Mode A)

Hub attivo: **windows-pc** · LAN `192.168.1.73` · brain WSL `:8001`

## Mattina — avvio hub (Windows PC)

1. Tray JANIS (icona **J**) → **Avvia tutto** — oppure:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\APP IA\JANIS\infra\wsl\start-janis-wsl.ps1"
   ```
2. Verifica locale:
   ```bash
   curl http://127.0.0.1:8001/api/status
   curl http://127.0.0.1:8001/api/vpn/status
   ```
3. Smoke WSL:
   ```bash
   bash ~/projects/J.A.N.I.S./infra/wsl/smoke-w2.sh
   bash ~/projects/J.A.N.I.S./infra/wsl/smoke-audit.sh
   ```

## LAN (casa, stessa rete)

| Cosa | URL / comando |
|------|----------------|
| HUD | http://192.168.1.73:8001/server?v=hudcli08 |
| Brain status | http://192.168.1.73:8001/api/status |
| Fleet nodi | http://192.168.1.73:8001/api/fleet/nodes |
| Pocket brain URL | `http://192.168.1.73:8001` |

## Esterno (fuori casa) — WireGuard

1. **Router**: UDP `51820` → `192.168.1.73` (Windows PC)
2. **Windows** (Admin): `infra/windows/setup-wireguard-forward.ps1`
3. **WSL**: `sudo bash infra/wsl/setup-wireguard.sh`
4. **Endpoint** client: `<IP_pubblico_o_DDNS>:51820` in `client.conf`
5. iPhone/iPad: WireGuard ON → stesso brain URL `http://192.168.1.73:8001`

Peer **iphone-14-pro**: tunnel `10.8.0.11` · config in `infra/vpn/peers/iphone-14-pro/client.conf`

Test fuori casa:
- Wi‑Fi OFF · VPN ON
- Safari → http://192.168.1.73:8001/api/status
- Pocket → Impostazioni → test connessione

## Mac Mini (`mac-node`)

```bash
ssh janzu@192.168.1.74
cd ~/projects/J.A.N.I.S. && git pull
bash infra/mac/install-fleet-bridge.sh
```

Verifica da Windows/WSL:
```bash
curl http://192.168.1.73:8001/api/fleet/nodes
# mac-node deve comparire online
```

## iPhone 14 Pro — build device

UDID: `00008120-0011759C1E40201E` · Team: `GVSL58WX9R`

Su Mac:
```bash
cd ~/projects/J.A.N.I.S./apps/pocket
xcodebuild -scheme JANICEPocket -destination 'id=00008120-0011759C1E40201E' \
  -derivedDataPath ~/Library/Developer/Xcode/DerivedData/JANIS-Pocket build
```

## Troubleshooting rapido

| Problema | Azione |
|----------|--------|
| Brain offline LAN | Tray → Riavvia brain · `bash infra/wsl/start-brain.sh` |
| Ollama offline | `infra/wsl/start-ollama-windows.ps1` |
| Mac non in fleet | `launchctl kickstart -k gui/$(id -u)/ai.janzulino.janis.fleet-bridge` |
| VPN ok, brain no | Verifica route `192.168.1.0/24` nel profilo WireGuard |
| Widget CodeSign | Team `GVSL58WX9R` su JANICEPocketWidgetExtension |

## API utili

- `GET /api/vpn/status` — hub, tunnel, hint setup
- `GET /api/fleet/nodes` — bridge Mac/worker
- `GET /api/presence` — dispositivi Pocket

Docs: `infra/vpn/README.md` · `apps/pocket/docs/WIREGUARD-VPN-SETUP.md` · `docs/FLEET-DEVICES.md`
