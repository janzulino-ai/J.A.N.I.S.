# JANIS — tray Windows

Icona nella **system tray** che avvia e monitora:

- **Ollama** (Windows, porta 11434)
- **Brain** (WSL Ubuntu, porta 8001)

## Installazione (una volta)

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\APP IA\JANIS\infra\windows\install-tray-autostart.ps1"
```

Cosa fa:

1. Crea collegamento in **Avvio** (`Startup`) → parte con Windows
2. Avvia la tray subito (icona **J** vicino all’orologio)

## Menu tray

| Voce | Azione |
|------|--------|
| **Apri HUD** | Browser → dashboard JANIS |
| **Avvia tutto** | Ollama + brain WSL |
| **Riavvia brain** | Stop/start brain in WSL |
| **Avvio con Windows** | Toggle autostart |
| **Esci tray** | Chiude solo l’icona (servizi restano attivi) |

## Avvio manuale (senza install)

Doppio click su `start-janis-tray.vbs` (nessuna finestra console).

## Log

`C:\APP IA\JANIS\data\tray\tray.log`

## Requisiti

- WSL Ubuntu con brain già configurato (`~/janis-venv`, symlink progetto)
- Ollama installato su Windows
