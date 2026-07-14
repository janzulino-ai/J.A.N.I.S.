# JANIS Desktop — app nativa Windows (Visual Studio)

Client **WPF .NET 8** che orchestra stack WSL + Ollama e offre UI tipo assistente commerciale (Cursor / Claude / Perplexity / Ollama locale).

## Aprire in Visual Studio

1. **Visual Studio 2022** (17.8+) con workload **.NET desktop**
2. Apri `apps/janis-windows/JANIS.Windows.sln`
3. Imposta **JANIS.Desktop** come progetto di avvio
4. **F5** (Debug)

Prerequisito runtime: [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) (incluso in Win11).

## Sezioni app

| Sezione | Funzione |
|---------|----------|
| **Agent** | Chat nativa — JANIS (tool+Ollama) · **Cursor Agent** (codice) · **Cursor Chat** |
| **Requisiti** | Verifica WebView2, WSL, Ollama, brain, venv — Fix / Avvia tutto |
| **Chat** | WebView2 → brain `/brain?device_id=janis-desktop` (WS + tool) |
| **HUD / Anteprima** | Dashboard kiosk live (`/server?v=hudcli08`) |
| **Terminale** | Shell WSL + PowerShell via `/api/hud/terminal` |
| **Browser** | WebView2 navigazione libera |
| **Plugin / Tool** | Elenco tool attivi dal brain (local-first) |
| **Impostazioni** | URL brain, runtime JSON, autostart tray |

## Tray

Chiudendo la finestra (X) l'app resta in **system tray**. Menu: Mostra, HUD, Avvia stack, Esci.

## Build release

```powershell
cd "C:\APP IA\JANIS\apps\janis-windows"
dotnet build JANIS.Desktop\JANIS.Desktop.csproj -c Release
```

Output: `JANIS.Desktop\bin\Release\net8.0-windows\JANIS.exe`

## Variabile ambiente

```powershell
$env:JANIS_ROOT = "C:\APP IA\JANIS"
```

## Roadmap (auto-implementazione)

- [ ] Chat nativa (no WebView) con streaming WS
- [ ] Pannelli multi-terminal (tab)
- [ ] Plugin store da `capability_gaps.json`
- [ ] Installer WiX / MSIX con bootstrap requisiti
- [ ] Integrazione Cursor API quando abilitata in runtime
- [ ] Sezione Perplexity / web search via brain tools

## Architettura

```
JANIS.exe (WPF)
  ├── RequirementsService → WebView2 / WSL / Ollama / brain
  ├── StackOrchestrator   → infra/wsl/start-janis-wsl.ps1
  └── JanisBrainClient    → http://127.0.0.1:8001/api/*
         ↕
Brain WSL (FastAPI) + Ollama Windows
```

Il brain resta la **source of truth** per LLM, tool e memoria — l'app Windows è shell + orchestrazione (come Cursor client → backend).

## Cursor API

1. Apri **Agent** → incolla `CURSOR_API_KEY` → **Salva + abilita PRO**
2. Scegli modalità:
   - **JANIS** — WebSocket, tool locali, Ollama (default)
   - **Cursor Agent** — `cursor-sdk` modifica codice nel repo (delega a Windows se brain è WSL)
   - **Cursor Chat** — ragionamento via Cursor API
3. API brain: `GET /api/cursor/status`, `POST /api/cursor/agent`, `POST /api/cursor/chat`

Richiede **Python 3.12 su Windows** con `cursor-sdk` (`pip install -r packages/brain/requirements.txt`) per agent da WSL.
