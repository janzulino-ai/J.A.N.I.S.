# J.A.N.I.S. — brain Linux server

## Architettura

| Nodo | Ruolo |
|------|--------|
| **Server Linux** | Brain primario :8001, Ollama, memoria, orchestrazione |
| **HDMI motherboard** | Kiosk `/server` (127.0.0.1) |
| **win-vm** | Windows in VM sulla stessa macchina (HDMI RTX) |
| **mac-node** | Fleet worker SSH |
| **Pocket** | Corpo iOS |

Windows **non** è brain — solo VM fleet.

## Env Linux

```bash
JANIS_PROJECT_DIR=/home/janis/projects/J.A.N.I.S./packages/brain
OLLAMA_BASE_URL=http://127.0.0.1:11434
API_DAILY_BUDGET_USD=2.0
```

## API Pocket v3.1

Vedi [API-CONTRACT.md](API-CONTRACT.md)
