# JANIS — Install sidecar (post W6–W7)

Il brain degrada senza questi binari. Dopo l’install, verifica con chat `janis doctor` o tool `janis_doctor`.

| Sidecar | Perché | Hint install |
|---------|--------|----------------|
| Ollama + modello chat/vision | ReAct + `describe_vision` | `ollama serve` · `ollama pull llava` |
| codebase-memory-mcp | `code_*` | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) |
| docling-mcp | `doc_read` | `pip/uv` package docling-mcp |
| officecli | `office_edit` | `officecli` + `officecli mcp` |
| ComfyUI `:8188` | `image_gen` / `video_gen` | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) · set `COMFYUI_URL` |
| SearXNG `:8080` | `research` fallback | Docker searxng · set `SEARXNG_URL` |
| ii-researcher-mcp | deep research | optional MCP `research` |
| agent-reach | `reach` | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) CLI |
| vision-mcp | OCR/video | optional; fallback Ollama |
| mobile-mcp (Mac) | `mobile_ui` | sul Mac Mini + fleet |

Config tipica `.env` brain:

```
MCP_ENABLED=true
HEARTBEAT_ENABLED=true
COMFYUI_URL=http://127.0.0.1:8188
SEARXNG_URL=http://127.0.0.1:8080
DOCTOR_HEAL_ENABLED=true
```

Manifest: `packages/brain/data/mcp/servers.json`.
