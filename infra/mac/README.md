# Mac Mini — fleet bridge verso brain Windows/WSL

## Prerequisito Windows (una volta, come Admin)

Sul PC Windows hub (`192.168.1.73`):

```powershell
# doppio click o da PowerShell admin:
infra\windows\setup-lan-forward-admin.cmd
```

Senza questo passo il Mac non raggiunge `:8001` sulla LAN (WSL è solo localhost).

## Install bridge

```bash
ssh janzu@mac-mini-di-janzu.local
cd ~/projects/J.A.N.I.S.
git pull
JANIS_HUB_LAN_IP=192.168.1.73 bash infra/mac/install-fleet-bridge.sh
```

## Verifica

```bash
curl http://192.168.1.73:8001/api/fleet/nodes
# deve mostrare mac-node online

tail -f ~/Library/Logs/janis/fleet-bridge.log
```

## Servizio

- LaunchAgent: `ai.janzulino.janis.fleet-bridge`
- Log: `~/Library/Logs/janis/fleet-bridge.log`
- Hub: `ws://192.168.1.73:8001/ws/fleet-node`
