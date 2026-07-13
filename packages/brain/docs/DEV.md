# Sviluppo JANIS

## Visual Studio 2022 (consigliato)

1. Installa **Python development** workload in Visual Studio Installer
2. Apri `JANIS.sln` (doppio click o File → Open → Project/Solution)
3. Seleziona interprete Python 3.12 (View → Python Environments)
4. Menu **Debug → Start Debugging (F5)** oppure scegli profilo dal dropdown:
   - **JANIS — Backend + Browser (F5)** — hot-reload + browser automatico
   - **JANIS — Finestra Desktop** — simulatore app nativa (pywebview)
   - **JANIS — Solo Backend** — API senza browser

URL dev: http://127.0.0.1:8001/?mode=browser

## Cursor / VS Code

Apri cartella `C:\APP IA\JANIS` → Run and Debug → profilo JANIS.

## Prerequisiti

```powershell
cd "C:\APP IA\JANIS"
pip install -r requirements.txt
copy .env.example .env
```

Ollama attivo con modello locale (`gemma4:latest` o simile).

## Struttura dev

```
dev/start_backend.py   → entry F5 (uvicorn reload)
dev/start_desktop.py   → backend + shell finestra
backend/               → API, brain, tools
frontend/              → UI (servita staticamente dal backend)
desktop/               → pywebview overlay/finestra
```
