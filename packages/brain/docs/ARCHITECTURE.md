# JANIS — Architecture

> **Just Another Neuralgic Improving Server**  
> Assistente AI locale-first per Windows 11 con overlay desktop, avatar 3D e loop di auto-miglioramento.

## Obiettivi di design

1. **Local-first** — Ollama (LLM), edge-tts (voce), strumenti file/terminale sul PC; nessun cloud obbligatorio.
2. **Sempre presente** — Shell desktop (tray + WebView trasparente) oltre al browser.
3. **Modulare** — Backend FastAPI, frontend Three.js, shell desktop separati; contratti HTTP/WebSocket chiari.
4. **Auto-miglioramento** — Gap di capacità registrati; `cursor_terminal` propone fix eseguibili localmente o via Cursor SDK.

---

## Vista d'insieme

```
┌─────────────────────────────────────────────────────────────────┐
│                     Windows Desktop                              │
│  ┌──────────────┐    ┌─────────────────────────────────────┐   │
│  │ System Tray  │───▶│ desktop/shell.py (pywebview/Edge)    │   │
│  │ Show/Hide    │    │  • overlay trasparente frameless       │   │
│  │ Mute/SS/Esci │    │  • idle monitor → screensaver          │   │
│  └──────────────┘    └──────────────┬──────────────────────────┘   │
│                                     │ http://localhost:8001        │
│  ┌──────────────────────────────────▼──────────────────────────┐  │
│  │ Frontend (Three.js + Web Speech + getUserMedia)              │  │
│  │  • Avatar GLB + Knowledge Ball                               │  │
│  │  • Patrol verticale (overlay/screensaver)                    │  │
│  │  • Stati: IDLE|WALKING|LISTENING|THINKING|ACTING|SPEAKING    │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────────┘
                              │ WebSocket /ws/janis
                              │ REST /api/*
┌─────────────────────────────▼──────────────────────────────────────┐
│ Backend FastAPI :8001                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ brain.py    │  │ tools/       │  │ capability_gaps.json    │  │
│  │ ReAct loop  │──│ registry     │──│ + /api/gaps             │  │
│  │ Ollama chat │  │ terminal,    │  │ cursor_terminal tool    │  │
│  └─────────────┘  │ filesystem,  │  └─────────────────────────┘  │
│                   │ cursor_*     │                                  │
│                   └──────────────┘                                  │
│  ┌─────────────┐  ┌──────────────┐                                 │
│  │ edge-tts    │  │ desktop_state│  ← mode, mute, idle             │
│  │ /api/tts    │  │ /api/desktop │                                 │
│  └─────────────┘  └──────────────┘                                 │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Ollama :11434      │
                    │ (gemma4, embed)    │
                    └───────────────────┘
```

---

## Componenti

### 1. Backend (`backend/`)

| Modulo | Ruolo |
|--------|--------|
| `main.py` | FastAPI app, static frontend, router |
| `core/brain.py` | Loop ReAct: LLM router → JSON tool/final → esecuzione |
| `core/llm_router.py` | Multi-provider: Ollama (default), OpenRouter fallback |
| `core/security.py` | Validazione path workspace, blocco comandi pericolosi |
| `core/knowledge_graph.py` | Grafo memorie con id → nodi Three.js |
| `core/tools/registry.py` | Registro strumenti; context per streaming Cursor |
| `core/tools/cursor_terminal.py` | Self-healing: registra gap, propone/esegue fix |
| `core/capability_gaps.py` | Persistenza gap in `capability_gaps.json` |
| `core/desktop_state.py` | Stato overlay/screensaver condiviso |
| `routers/websocket.py` | `/ws/janis` — chat, stati, knowledge |
| `routers/gaps.py` | `/api/gaps` — CRUD gap |
| `routers/desktop.py` | `/api/desktop/*` — mode, mute, idle |
| `routers/pages.py` | `/api/projects`, `/api/settings`, `/api/memory/*`, `/api/setup/status` |

### 2. Frontend (`frontend/`)

| File | Ruolo |
|------|--------|
| `app.js` | Three.js scene, WebSocket, TTS coda, nav sidebar |
| `janis-brain.js` | Second brain 3D, raycast click nodi |
| `janis-panel.js` | Window manager, pannelli cursor/whatsapp, layout localStorage |
| `janis-pages.js` | Pagine Lavori/Progetti/Impostazioni, wizard setup |
| `janis-shell.css` | Layout IDE tipo Cursor |
| `index.html` | Shell sidebar + chat + agent zone |

**Modalità display** (query `?mode=`):

- `browser` — sessione completa con orbit controls
- `overlay` — finestra laterale, patrol attivo, HUD ridotta
- `screensaver` — fullscreen idle, patrol low-power, HUD minimale

### 3. Desktop shell (`desktop/`)

| File | Ruolo |
|------|--------|
| `shell.py` | Entry point: pywebview (preferito) o Edge fallback |
| `idle.py` | `GetLastInputInfo` → secondi idle Windows |

**Tray menu:** Mostra, Nascondi, Screensaver, Mute, Esci.

### 4. Avvio (`start.ps1`)

1. Ollama (se non in esecuzione)
2. Backend uvicorn :8001
3. `python -m desktop.shell`

---

## Flussi dati

### Voce in ingresso (local-first)

```
Microfono PC
    → getUserMedia (WebView/Edge)
    → Web Speech API (it-IT)
    → WebSocket chat_message
    → brain.process_message
    → Ollama + tools
```

Fallback futuro (Phase 2): `sounddevice` + Whisper locale su backend se Web Speech non disponibile.

### Voce in uscita

```
Risposta finale
    → edge-tts (/api/tts) — MP3 locale via Microsoft Neural
    → fallback Web Speech API
```

### Self-improvement loop

```
Tool fallisce / non esiste
    → log_gap() → capability_gaps.json
    → LLM usa cursor_terminal
        → execute=false: proposta all'utente
        → execute=true: terminal locale
        → use_cursor=true: Cursor SDK (CURSOR_API_KEY)
    → resolve_gap on success
```

Endpoint: `GET /api/gaps`, `POST /api/gaps`, `POST /api/gaps/{id}/resolve`.

---

## Strategia local-first

| Capacità | Implementazione | Cloud |
|----------|-----------------|-------|
| Ragionamento | Ollama locale (+ OpenRouter opzionale) | Solo se API key |
| TTS | edge-tts (Microsoft edge voices) | Solo sintesi MS, no LLM cloud |
| STT | Web Speech API nel browser | Dipende da engine browser* |
| Memoria | JSON locale `data/memory/` | No |
| Codice | terminal + cursor_code opzionale | Solo se API key Cursor |

\*Su Edge/Chromium spesso usa servizio cloud speech; Phase 2: Whisper locale.

---

## Stati avatar (state machine)

```
                    ┌─────────┐
         idle ─────▶│ WALKING │◀── overlay/screensaver patrol
                    └────┬────┘
                         │ voice / chat
                    ┌────▼────┐
                    │LISTENING│
                    └────┬────┘
                         │
                    ┌────▼────┐     ┌────────┐
                    │ THINKING│────▶│ ACTING │ (tools)
                    └────┬────┘     └───┬────┘
                         │              │
                    ┌────▼──────────────▼────┐
                    │       SPEAKING         │
                    └───────────┬────────────┘
                                │
                           ┌────▼────┐
                           │  IDLE   │
                           └─────────┘
```

---

## Phase 2 (pianificato)

Vedi anche `docs/LINUX.md` per porting Linux.

- [ ] Click-through overlay (WS_EX_TRANSPARENT) su Windows
- [ ] Whisper + sounddevice backend STT
- [ ] Animazioni GLB skeletal (walk cycle reale vs bob patrol)
- [ ] Wake word locale
- [ ] Multi-monitor patrol
- [ ] TripoSR avatar pipeline integrata — vedi `scripts/triposr_to_glb.py`
- [ ] Notifiche Windows native

---

## Avatar 3D (TripoSR)

Pipeline locale per mesh 360° da `frontend/assets/janis-texture.png`:

```powershell
# Setup una tantum
.\scripts\setup_triposr.ps1

# Genera janis.glb (GPU consigliata, ~15s dopo download modello)
& ".\tools\triposr-venv\Scripts\python.exe" .\scripts\triposr_to_glb.py
```

Fallback euristico (depth map, no GPU): `python scripts/image_to_glb.py`

**Nota Windows:** `torchmcubes` non compila senza CUDA Toolkit; lo script usa patch scikit-image per marching cubes.

---

## Test manuale

1. `.\start.ps1` — backend + tray + overlay
2. Tray → **Mostra JANIS** — avatar sul bordo destro che cammina
3. Tray → **Screensaver** — fullscreen patrol
4. 🎙 — parla; verifica LISTENING → THINKING → SPEAKING
5. `curl http://localhost:8001/api/gaps` — lista gap
6. Chiedi a JANIS di usare uno strumento inesistente → gap registrato
7. `curl http://localhost:8001/api/desktop/state` — mode/mute/idle

---

## Requisiti / blocker utente

| Requisito | Note |
|-----------|------|
| Python 3.10+ | Backend + desktop shell |
| Ollama + modello | es. `gemma4:latest` |
| Edge o pywebview | WebView2 runtime (Windows 11) |
| Permessi microfono | Windows Privacy → Microphone |
| `CURSOR_API_KEY` | Opzionale, per auto-programmazione |
| `pip install -r requirements.txt` | pywebview, pystray, Pillow |

---

## Convenzioni

- Nome prodotto: **JANIS** (non JARVIS)
- Porta backend: **8001**
- WebSocket: **/ws/janis**
- Workspace agente: `JANIS_WORKSPACE` in `.env`
