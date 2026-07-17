# JANIS — Install sidecar (Mode A · post W6–W7)

Il brain degrada senza questi binari. Dopo l’install: chat `janis doctor`, tool `janis_doctor`, o `GET /api/doctor`.

## Ordine consigliato (Windows hub + WSL brain)

1. **Ollama Windows** su `:11434` (tray / `infra/wsl/start-ollama-windows.ps1`)
2. **Brain WSL** `:8001` (`infra/wsl/start-brain.sh` o tray)
3. **MCP CLI** in WSL — `bash infra/sidecars/install-mcp-clis.sh`  
   Priorità: `codebase-memory-mcp` (doctor lo tratta come required)
4. **ComfyUI Windows** `:8188` — `infra/sidecars/install-comfyui-windows.ps1`
5. **SearXNG** `:8080` — `docker compose -f infra/sidecars/docker-compose.searxng.yml up -d`
6. **URL cross-boundary** — da WSL: `bash infra/wsl/configure-sidecar-urls.sh`  
   (imposta `COMFYUI_URL` / `SEARXNG_URL` verso IP gateway Windows, non `127.0.0.1` se i servizi sono su Windows)
7. Riavvia brain → verify sotto

Avvio rapido SearXNG (+ reminder Comfy): `bash infra/sidecars/start-capability-sidecars.sh`  
oppure da PowerShell: `infra/sidecars/start-capability-sidecars.ps1`

## Tabella sidecar

| Sidecar | Perché | Hint install |
|---------|--------|----------------|
| Ollama + modello chat/vision | ReAct + `describe_vision` | `ollama serve` · `ollama pull llava` |
| codebase-memory-mcp | `code_*` | `install-mcp-clis.sh` / [DeusData](https://github.com/DeusData/codebase-memory-mcp) |
| docling-mcp | `doc_read` | `install-mcp-clis.sh` |
| officecli | `office_edit` | `install-mcp-clis.sh` |
| ComfyUI `:8188` | `image_gen` / `video_gen` | `install-comfyui-windows.ps1` · `COMFYUI_URL` |
| SearXNG `:8080` | occhi web meta-search | `docker-compose.searxng.yml` · `SEARXNG_URL` |
| Ollama | sintesi report `research` | già Mode A — pipeline **SearXNG + Ollama** (no iscrizione) |
| ii-researcher | deep research cloud | **non default** — richiede Tavily/SerpAPI |
| agent-reach | `reach` | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) CLI |
| vision-mcp | OCR/video | optional; fallback Ollama |
| mobile-mcp (Mac) | `mobile_ui` | sul Mac Mini + fleet (dopo A) |

## Config `.env` brain

Vedi `packages/brain/.env.example`:

```
MCP_ENABLED=true
HEARTBEAT_ENABLED=true
DOCTOR_HEAL_ENABLED=true
COMFYUI_URL=http://<IP-WINDOWS>:8188
SEARXNG_URL=http://<IP-WINDOWS>:8080
```

Manifest MCP: `packages/brain/data/mcp/servers.json`.

## Verify

Target: **verde** (nessun required fail e &lt;3 optional fail). Smoke completo:

```bash
# WSL — script unico (doctor + capabilities + tool smoke)
bash infra/sidecars/verify-mode-a.sh

# oppure solo HTTP doctor
curl -s http://127.0.0.1:8001/api/doctor | jq .summary,.required_fail,.optional_fail

# oppure da packages/brain
cd packages/brain && PYTHONPATH=. python scripts/verify_mode_a.py
```

Smoke tool (inclusi in verify-mode-a):

- tool `mcp_status`
- tool `research_status` + `research` (query corta)
- tool `media_status`
- `GET /api/capabilities?wave=1`
- `GET /api/media/images`

Ordine install consigliato prima del verify:

1. Ollama Windows `:11434`
2. Brain WSL `:8001`
3. `bash infra/sidecars/install-mcp-clis.sh`
4. ComfyUI Windows `:8188` · SearXNG Docker `:8080`
5. `bash infra/wsl/configure-sidecar-urls.sh` → riavvia brain
6. `bash infra/sidecars/verify-mode-a.sh`

Glances / LiteLLM / Qdrant restano su `infra/sidecars/install-sidecars.sh` + `start-all.sh` (separati da Comfy/SearXNG).
