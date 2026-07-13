# Handoff sessione — JANIS Pocket + Brain (2026-06-22)

> Per l'agente Cursor sulla cartella **JANIS** (app madre).  
> Lavoro coordinato con agente su **JANIS-Pocket** (satellite iOS).

## Obiettivo architetturale

- **Brain** (JANIS Windows `:8001`) = fisso: FastAPI + Ollama + memoria
- **Presenza** = mobile (dove vedi/parli con JANIS)
- **Conversazione** = segue presenza (`session_id` unica)
- **Pocket** = input sensoriale mobile (voce → STT → brain)
- **Terminali** = visibili stile Cursor (`wt.exe` / WSL), non subprocess nascosto
- **UI desktop** = widget chat + tray (non più IDE unica di default)

## Commit GitHub (pushati da Windows)

| Repo | Commit | Contenuto |
|------|--------|-----------|
| `janzulino-ai/JANIS-Pocket` | `628e59f` | v1.1: `JanisAPIClient`, STT server, settings URL, branding J.A.N.I.C.E. |
| `janzulino-ai/JANIS` | `ea1802c` | presence, AgentHost, widget, Pocket API, WSL, autonomy loop |

## Implementato in JANIS (brain)

### Nuovi moduli
- `backend/core/presence.py` + `routers/presence.py` — claim/migrate, dormant monitor
- `backend/core/agent_host.py` + `routers/agents.py` — terminali OS visibili
- `backend/core/tools/terminal_visible_tool.py`, `terminal_smart`, `wsl_tool.py`
- `backend/routers/pocket.py` — `POST /api/pocket/ingest`
- `backend/core/device_auth.py` — header `X-JANIS-Token` (opzionale)
- `backend/core/autonomy_loop.py` — reflect periodico su gap
- `frontend/widget.html|js|css` — chat compatta
- `desktop/shell.py` + `launcher.py` — default **widget mode** + tray esteso

### API chiave per Pocket
- `POST /api/stt` — m4a supportato (faster-whisper)
- `POST /api/presence/claim` — `{device_id: "pocket", surface: "mobile"}`
- `POST /api/pocket/ingest` — testo → `remember`
- `GET /api/status` — ping connessione

### Config `.env` (nuovo)
```
JANIS_DEVICE_TOKEN=   # opzionale; vuoto = LAN dev senza auth
AUTONOMY_ENABLED=true
AUTONOMY_REFLECT_ENABLED=true
AUTONOMY_AUTODEV_ENABLED=false
```

### Avvio PC
```powershell
cd "C:\APP IA\JANIS"
python -m desktop.launcher   # widget + tray, backend :8001
```

## Implementato in JANIS-Pocket (satellite)

- `JanisAPIClient.swift` — STT, presence claim, ingest, ping
- `SettingsView` — **Server JANIS — obbligatorio** + Test connessione
- STT ordine: server JANIS → Whisper cloud → Apple Speech
- Display name: **J.A.N.I.C.E.** · versione **1.1 (2)**
- `NSAllowsLocalNetworking` in Info.plist

### Test iPhone
1. Impostazioni → `http://192.168.1.72:8001` → Test connessione
2. Registra nota → engine `janis` (sync brain anche con fallback STT)
3. Brain avviato: `python -m desktop.launcher` (2026-06-22)

### Verifiche brain (2026-06-22)
- `GET /api/status` → OK (Ollama online, v2.0.0)
- `GET /api/stt/diagnostic` → faster-whisper ready, m4a supportato
- `POST /api/presence/claim` pocket/mobile → OK
- `POST /api/pocket/ingest` → OK (remember)
- LAN `http://192.168.1.72:8001` → raggiungibile

## Sync Mac Mini

- Path: `/Users/janzu/Documents/JANIS-Pocket`
- `git pull` fallisce (HTTPS senza credenziali GitHub)
- File v1.1 copiati via **scp** da Windows (2026-06-22)
- Dopo pull/scp: Xcode Clean Build → verificare **Versione 1.1 (2)** in Impostazioni

## CI GitHub

- `.github/workflows/ci.yml` lancia `pytest` su push — **fallisce** (`PYTHONPATH` mancante)
- GitHub = archivio/ponte; CI è opzionale (disabilitabile)

## Gap / prossimi passi

| Area | Stato |
|------|-------|
| Pocket ↔ Brain sync | API pronta; iPhone deve avere build 1.1 |
| Presenza cross-device | Service ok; da raffinare TTS routing |
| Terminali visibili | AgentHost ok; brain deve usare `terminal_visible` |
| Autosufficienza piena | Loop reflect ok; autodev auto ancora off |
| Coordinatore always-on | Aperto: Mac Mini vs Windows |
| OSS upgrade | Piper TTS, Qdrant — non fatto |

## Decisioni utente

- Nome device: **J.A.N.I.C.E.** · repo: **JANIS-Pocket**
- Lavoro satelliti in chat Pocket; app madre in chat JANIS
- No marketing; dati precisi; proposte prima di agire (salvo richiesta esplicita)

## File canvas (Cursor)

- `canvases/janis-ecosistema-proposta.canvas.tsx` — architettura v3
- `canvases/pocket-sync-diagnostica.canvas.tsx` — diagnosi sync iPhone

---

*Aggiornare questo file a fine sessione se cambia lo stato.*
