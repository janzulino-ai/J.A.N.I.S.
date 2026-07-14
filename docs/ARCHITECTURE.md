# J.A.N.I.S. — brain Linux server

## Architettura attuale (Modalità A)

| node_id | Nodo | Ruolo |
|---------|------|--------|
| **wsl-brain** | WSL2 Ubuntu su Windows MSI | Brain :8001 · hub operativo |
| **windows-pc** | MSI i9 · RTX 3080 Ti | Ollama · app desktop WPF · tray · dev Cursor |
| **mac-node** | Mac Mini M4 | Worker fleet · bridge WS |
| **iphone-15-pro-max** | iPhone 15 Pro Max | JANIS Pocket · organi iOS |

**Target fase 2 (Modalità B):** **linux-server** su Samsung 970 EVO · Debian 12 nativo · hub permanente.

Inventario completo: [FLEET-DEVICES.md](FLEET-DEVICES.md)

## Stack Modalità A (attiva)

```
Windows 11
├── Ollama (gemma4 · qwen · llama70b)
├── JANIS Desktop (WPF · Agent · HUD · terminale)
└── WSL2
    └── brain :8001 (ReAct · tool · memoria · /api/cursor)
        ├── HUD /server (hudcli08)
        └── Pocket iOS (LAN)
```

## App Windows

- Solution: `apps/janis-windows/JANIS.Windows.sln`
- Sezione **Agent**: JANIS (WS) · Cursor Agent · Cursor Chat
- Bridge: `GET /api/cursor/status` · `POST /api/cursor/agent`

## LLM Auditor (W5 — planned)

Confronto Ollama vs teacher (Gemini/Cursor) → reasoning gap · prompt tuning · Modelfile.
Integrazione: `llm_lab/` harvest → audit → curate → eval → export.

## Env WSL



```bash

JANIS_PROJECT_DIR=/home/janis/projects/J.A.N.I.S./packages/brain

OLLAMA_BASE_URL=http://127.0.0.1:11434

API_DAILY_BUDGET_USD=2.0

```



## VPN esterna



WireGuard sul server · peer iOS + Zenbook · vedi `infra/vpn/README.md`



## API Pocket v3.1



Vedi [API-CONTRACT.md](API-CONTRACT.md)

