# JANIS Shell Chromium

JANIS **non usa** Chrome, Firefox o Edge come app esterna.

## Motore attuale: WebView2 (Chromium)

La shell desktop (`desktop/shell.py`) usa **pywebview** con:

```python
webview.start(gui="edgechromium")
```

WebView2 è il runtime **Chromium** di Microsoft (stesso motore di Edge). È il modo standard su Windows 11 per embeddare una webapp in una finestra nativa.

```
┌─────────────────────────────┐
│  JANIS.exe / python shell  │
│  ┌─────────────────────────┐│
│  │ WebView2 (Chromium)     ││
│  │  → frontend/index.html  ││
│  └─────────────────────────┘│
└─────────────────────────────┘
         ↕ localhost:8001
┌─────────────────────────────┐
│  Backend FastAPI (Python)   │
└─────────────────────────────┘
```

## Avvio

| Comando | Terminale | Uso |
|---------|-----------|-----|
| `.\start-janis-app.ps1` | **Nascosto** | Uso quotidiano |
| `python -m desktop.launcher` | Nascosto | Idem |
| `python -m desktop.launcher --console --reload` | Visibile | Dev / F5 VS |
| F5 **JANIS App** | Terminale VS integrato | Debug con log |

Log backend: `data/backend.log` · Log launcher: `data/launcher.log`

## Requisito

**WebView2 Runtime** — già incluso in Windows 11. Se manca:
https://developer.microsoft.com/microsoft-edge/webview2/

## Fase futura: Chromium embedded completo (CEF)

Se in futuro vuoi **bundlare** Chromium dentro l'installer (senza dipendere da WebView2 di sistema):

| Opzione | Pro | Contro |
|---------|-----|--------|
| **CEF Python** (cefpython3) | Controllo totale, stesso Chromium | +150 MB, build complessa |
| **Electron** | Ecosistema enorme | App pesante (~100 MB+) |
| **WebView2** (attuale) | Leggero, nativo Win11 | Dipende runtime Microsoft |

Per JANIS fase 1, WebView2 è la scelta giusta: Chromium reale, finestra tua, zero barra browser.

## Personalizzazione shell

- Titolo finestra: `WINDOW_TITLE` in `desktop/shell.py`
- User-Agent: `USER_AGENT` (identifica JANIS nel frontend)
- Modalità overlay fullscreen: `start-janis.ps1` (senza `--window`)
