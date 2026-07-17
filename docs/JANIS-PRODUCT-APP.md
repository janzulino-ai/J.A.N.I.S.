# JANIS — Product App (north star)

> App AI locale proprietaria, chat-first (ChatGPT / Claude / Cursor).  
> Tutto ciò che studiamo va **integrato dentro JANIS**, non lasciato come wrapper terzi.  
> Aggiornato: 2026-07-17

---

## North star

**JANIS è il prodotto.** Ollama, ComfyUI, SearXNG (e MCP opzionali) sono **processi sidecar**.  
Logica, API, UX, Capability Fabric e tool restano di JANIS.

| Principio | Regola |
|-----------|--------|
| Verde = E2E | Una capacità è *green* solo se un percorso end-to-end funziona (sidecar integrato **o** fallback nativo JANIS) |
| No fake ready | `command_found` / riga in `servers.json` ≠ successo |
| Local first | Nessuna API search a pagamento / signup obbligatoria |
| Voice/chat first | Operazioni comuni controllabili a voce o chat, senza GUI obbligatoria |
| Mode A → B | Oggi WSL brain + Windows app; domani Linux di sistema (senza wipe SSD2 accidentale) |

---

## UX shell

```
┌─────────────┬──────────────────────────────┬─────────────┐
│ Brand/nav   │  Chat (testo + voce)         │ Cap rail    │
│ Brain viz   │  stream + tool events        │ ●●● status  │
│ Agents      │  media inline                │ Fabric E2E  │
└─────────────┴──────────────────────────────┴─────────────┘
```

- **Chat** = superficie primaria (HUD `/server`, Windows Agent, `/client`).
- **Capability rail** = stato Fabric da `GET /api/capabilities` (verde solo E2E).
- **HUD** = shell kiosk Mode B; **Windows Agent** = Mode A client.

---

## Capability Fabric

API: `GET /api/capabilities?wave=1`

| id | Ownership | Backend ready |
|----|-----------|---------------|
| `chat` | JANIS | Ollama |
| `code_search` | hybrid | DeusData MCP **o** ripgrep/pathlib |
| `doc_read` | hybrid | Docling MCP **o** testo/PDF nativo |
| `vision` | hybrid | vision-mcp **o** Ollama vision |
| `research` | JANIS | `local_research` (SearXNG + Ollama) |
| `image_gen` | hybrid | ComfyUI + `/api/media` |
| `media_api` | JANIS | serving `/api/media/images` |
| `voice` | JANIS | STT faster-whisper + TTS + mic→chat |

Doctor (`GET /api/doctor` / tool `janis_doctor`) legge il Fabric: non marca MCP “ok” senza `session_active`.

---

## Sidecar vs JANIS-owned

| Sidecar (processo) | JANIS-owned |
|--------------------|-------------|
| Ollama | ReAct, intent, tools, Fabric |
| ComfyUI | `image_gen`, `/api/media` |
| SearXNG | `local_research` / `research` |
| MCP stdio (opz.) | bridge + fallback nativi |
| — | HUD, Agent WPF, Pocket API |

---

## Mode A → Mode B

| Mode | Host | UI |
|------|------|-----|
| **A** (ora) | WSL brain + Windows app | Agent WPF + browser HUD |
| **B** (target) | Debian/JANIS OS su SSD2 | HUD kiosk fullscreen + voce |

Gate disco: [`MODE-B-SSD2-GATE.md`](MODE-B-SSD2-GATE.md) — **mai wipe senza digitare `WIPE`**.  
Build ISO: [`TESTER/README.md`](../TESTER/README.md).  
Post-install senza wipe: `scripts/mode-b-bootstrap.sh` dopo Debian netinst.

---

## Voice / chat control (primario)

Stesso pipeline: **voce → STT → chat WS/HTTP → tools → TTS**.

Frasi utili (italiano):

| Detto / scritto | Effetto |
|-----------------|---------|
| «janis doctor» / «stato sistema» | `janis_doctor` / Fabric |
| «cerca nel codice …» | `code_search` |
| «leggi il file …» | `doc_read` |
| «ricerca …» | `research` (locale) |
| «genera un’immagine di …» | `image_gen` |
| «descrivi questa foto» | `describe_vision` |
| «capacità» / «cosa puoi fare» | risponde via Fabric |

### Dove parlare

1. **Client web** (`/client` o `/`) — pulsante 🎙 (Web Speech o Whisper backend)  
2. **HUD kiosk** (`/server`) — pulsante VOICE in chat  
3. **Windows Agent** — pulsante MIC → STT brain → stesso WebSocket chat  

TTS: toggle 🔊; risposte lette ad alta voce quando attivo.

---

## Wave list

### Wave 1 (questo sprint) — Fabric + fallback nativi

- [x] `capabilities.py` + `GET /api/capabilities`
- [x] Native `code_search` / `doc_read`
- [x] Doctor onesto + Fabric
- [x] HUD rail + tile CAPABILITY FABRIC (`hudcli10`)
- [x] Windows Agent capabilities rail
- [x] pytest Fabric + fallback
- [x] Wire `image_gen` / `/api/media` nello stato Fabric

### Wave 2 — Voice/chat primary

- [x] HUD voice → stesso `send()` chat
- [x] Windows Agent mic → `/api/stt` → chat
- [x] Doc controllo totale voce/chat (questa pagina)
- [ ] Continuous listen opzionale (push-to-talk default; hold mode follow-up)
- [ ] Wake-word «Janis» (opzionale)

### Wave 3 — Mode B Linux system

- [x] `packages.list` + systemd units brain/kiosk
- [x] Autostart HUD Chromium kiosk + voice-ready audio
- [x] `scripts/mode-b-bootstrap.sh` (no wipe)
- [x] Docs A→B
- [ ] ISO build eseguita su host Linux (script pronti)
- [ ] Wipe SSD2 solo con conferma utente esplicita

---

## Verify (breve)

```bash
cd packages/brain
# Fabric API
pytest tests/test_capabilities.py -q

# Smoke manuale
curl -s http://127.0.0.1:8001/api/capabilities | jq '.summary,.counts'
curl -s http://127.0.0.1:8001/api/doctor | jq '.summary,.fabric.counts'

# Voice STT
curl -s http://127.0.0.1:8001/api/stt/diagnostic | jq .

# HUD cache
# apri http://127.0.0.1:8001/server?v=hudcli10 — rail CAPS in header
```

Mode B (su Linux, **senza** `deploy-disk.sh`):

```bash
cd TESTER && sudo BUILD_FORCE=1 bash build-base.sh && sudo bash build-iso.sh
# Oppure Debian netinst su SSD2 →:
bash scripts/mode-b-bootstrap.sh
```
