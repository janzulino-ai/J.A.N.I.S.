# JANIS — Fase 2 Linux (pianificazione)

## Obiettivo

Port nativo Linux con stesso stack: FastAPI + frontend web + shell desktop.

## Approccio previsto

1. **Backend** — già cross-platform (Python/FastAPI)
2. **Desktop shell** — sostituire pywebview Win32 overlay con:
   - pywebview su X11/Wayland (finestra normale)
   - oppure Tauri/Electron wrapper leggero
3. **Distribuzione** — AppImage o `.deb` con systemd user service
4. **ISO JANIS OS** — fase successiva basata su Ubuntu/Debian minimal + autostart

## Stato attuale

Windows nativo — priorità stabilità prima del port.

## Prerequisiti futuri

- Ollama Linux
- WebView GTK (pywebview)
- Test suite CI su `ubuntu-latest`
