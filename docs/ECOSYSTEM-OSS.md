# JANIS — Ecosistema OSS (6 layer)

> Schema arricchito: costi LLM, risorse, API a pagamento, Tech Scout, MCP/canali.

## Layer 1 — Presenza

| Componente | Stack | Path |
|------------|-------|------|
| HUD server | HTML/CSS/JS | `packages/kiosk/` |
| Kiosk tty | pywebview / Firefox / Chromium | `infra/kiosk/` |
| Pocket iOS | Swift → FastAPI | repo JANIS-Pocket |
| Canali | Telegram polling, WhatsApp bridge | `backend/core/channels/` |

## Layer 2 — Brain

| Componente | Stack | Path |
|------------|-------|------|
| API | FastAPI :8001 | `packages/brain/backend/` |
| ReAct loop | brain.py + tool registry | `backend/core/brain.py` |
| Memoria file | JSON long_term | `data/memory/` |
| Memoria semantica | Qdrant + Ollama embed | `backend/core/qdrant_client.py` |

## Layer 3 — LLM plane

| Componente | OSS | Path |
|------------|-----|------|
| Default | Ollama | locale :11434 |
| Proxy unificato | LiteLLM | `infra/litellm/` |
| Fallback cloud | OpenRouter | `llm_router.py` |
| PRO coding | Cursor SDK | `cursor_llm.py` |
| Budget | cost_router | `backend/core/orchestrator/cost_router.py` |
| Usage log | llm_usage.json | `backend/core/llm_usage.py` |
| Paid catalog | paid_capabilities | `backend/core/paid_capabilities.py` |

**Env:** `API_DAILY_BUDGET_USD`, `LITELLM_PROXY_URL`, `OPENROUTER_API_KEY`, `CURSOR_API_KEY`

## Layer 4 — Capabilities

| Componente | Descrizione | Path |
|------------|-------------|------|
| Tool registry | ~35 tool statici | `backend/core/tools/` |
| MCP bridge | MCP → execute_tool | `backend/core/mcp_bridge.py` |
| Paid CLI | gh, cursor, git (allowlist) | `tools/paid_cli_tool.py` |
| Channel skills | manifest OpenClaw-style | `channels/skills_manifest.py` |
| Scout tool | discover/test/verify/promote | `tools/scout_tool.py` |

## Layer 5 — Infra

| Componente | OSS | Avvio |
|------------|-----|-------|
| Monitor | Glances | `infra/glances/start-glances.sh` |
| Vector DB | Qdrant Docker | `infra/qdrant/start-qdrant.sh` |
| LLM proxy | LiteLLM | `infra/litellm/start-litellm.sh` |
| Fleet | KVM win-vm, WS nodi | `infra/win-vm/` |
| TESTER | debootstrap + xorriso | (pianificato) |

**Metriche:** `GET /api/host/metrics` — CPU/RAM/GPU/disk/rete + history ring

## Layer 6 — Tech Scout

Pipeline: **discover → classify → sandbox test → verify → promote**

| Step | API / tool |
|------|------------|
| Discover | `POST /api/scout/discover`, `scout discover` |
| Test | `POST /api/scout/test/{id}`, `scout test` |
| Verify | `scout verify` |
| Promote | `POST /api/scout/promote/{id}` → research → reflect |
| Scheduler | job `weekly-tech-scout` (lunedì 06:00 UTC) |

**Dati:** `data/scout/candidates/`, `data/scout/watchlist.yaml`, `workspaces/sandbox/`

## Sidecar consigliati (ordine)

1. Glances — monitor risorse (`systemctl --user enable janis-glances`)
2. LiteLLM — gateway + costi (`janis-litellm`)
3. Qdrant — semantic_recall (`janis-qdrant`, binario nativo senza Docker)
4. Langfuse — opzionale; oggi si usa `data/llm_usage.json`

**Setup server:** `bash infra/sidecars/setup-systemd-user.sh`  
**Deploy completo:** `bash scripts/deploy-server.sh`  
**Unit user:** `janis-glances`, `janis-litellm`, `janis-qdrant`, `janis`  
**Linger:** `sudo loginctl enable-linger janis` (servizi attivi senza login)

## Limiti onesti

- Costi Cursor/OpenRouter: stima se provider non restituisce usage
- Scout sandbox: no sudo, timeout 120s, cleanup 24h
- MCP: manifest locale; server npm avviati on-demand
- WhatsApp: richiede bridge Node attivo (`WHATSAPP_BRIDGE_URL`)
