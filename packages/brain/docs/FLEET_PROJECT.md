# JANIS Fleet — progetto auto-sviluppo

> Documento di riferimento per JANIS quando implementa se stessa via `cursor_code` / `self_develop`.

## Obiettivo

JANIS controlla **tutti i PC super partes**: Windows, Mac Mini, futuri nodi.
- Routing task al nodo giusto (online, OS, dove sta il file)
- **Memoria condivisa** unica
- **Power management**: flotta accesa/spenta insieme (WOL + shutdown)
- Tu parli con **una sola JANIS**; lei orchestra

## Architettura target

```
Utente → UI (Windows) → Coordinatore (brain + memoria) → Nodi worker (WS)
                              ↓
                    fleet_execute / fleet_power
```

### Ruoli
| Nodo | Ruolo suggerito |
|------|-----------------|
| Mac Mini | Coordinatore + memoria (always-on quando flotta attiva) |
| Windows PC | UI principale + worker + dev pesante |
| Altri | Worker opzionali |

### Protocollo nodi (WebSocket)
- `WS /ws/fleet-node` — registrazione, heartbeat, capabilities
- Comandi: `fleet_command` → esecuzione tool locale → `fleet_result` streaming

### Memoria
- Fase 1: centralizzata sul coordinatore (`data/memory/`)
- Fase 2: sync verso cache nodi

### Power
- Tool `fleet_power`: wake | sleep | status
- WOL magic packet + shutdown ordinato
- Richiede `fleet.yaml` con MAC address e host per nodo

## Fasi implementazione (ordine)

1. **Fase 1 — Registro nodi**: `MacBridgeManager`, WS `/ws/fleet-node`, client `bridge/client.py`, UI nodi online
2. **Fase 2 — Esecuzione remota**: tool `fleet_execute`, pannelli per nodo
3. **Fase 3 — Memoria centralizzata**: remember/recall via coordinatore
4. **Fase 4 — Power fleet**: WOL + sleep coordinato
5. **Fase 5 — Router super partes**: LLM sceglie nodo per ogni task

## File chiave esistenti (da estendere, non riscrivere)

- `backend/routers/websocket.py` — ConnectionManager
- `backend/core/tools/cursor_agent.py` — pattern streaming
- `backend/core/brain.py` — ReAct loop
- `backend/core/tools/memory_tool.py` — memoria long-term
- `frontend/janis-panel.js` — pannelli agenti
- `frontend/app.js` — AGENTS map

## Nuovi file previsti

- `backend/core/fleet/manager.py`
- `backend/routers/fleet.py`
- `backend/core/tools/fleet_execute.py`
- `backend/core/tools/fleet_power.py`
- `bridge/client.py` (Mac/Windows headless node)
- `config/fleet.yaml.example`
- `backend/core/tools/self_develop.py` (orchestrazione auto-sviluppo)

## Domande aperte (JANIS: chiedi all'utente se non in project_state.json)

1. Coordinatore: Mac Mini o Windows?
2. Rete: LAN casa o Tailscale?
3. Mac Mini always-on come coordinatore, o entrambi sempre accesi/spenti insieme?
4. Primo tool remoto prioritario: terminal, file, o browser?

## Regole per Cursor Agent (quando implementi codice)

- Repo: `JANIS_PROJECT_DIR` (root JANIS)
- Match stile esistente: FastAPI, tool `@register`, frontend vanilla JS
- Diff minimi, una fase per sessione
- Non rompere Windows shell esistente
- Test: import backend.main, verificare route OpenAPI
