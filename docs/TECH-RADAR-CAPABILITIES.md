# JANIS — Tech radar capacità (scan GitHub 2026-07-16)

Obiettivi utente:

1. **Creare** immagini, video, codice + **ricerche attendibili**
2. **Vedere** video/foto e **leggere** documenti
3. **Usare tutti i dispositivi** disponibili

Approccio: MCP sidecar dove possibile (stesso modello DeusData / OfficeCLI).  
Prerequisito comune: **W6a MCP client reale** in [`INTEGRATION-MULTI-SOURCE.md`](INTEGRATION-MULTI-SOURCE.md).

---

## Mappa vs JANIS oggi

| Capacità | JANIS oggi | Gap residuo |
|----------|------------|-------------|
| Codice | ReAct + Cursor + tools `code_*` → DeusData MCP | Installare binario `codebase-memory-mcp` |
| Immagini/video **generazione** | `image_gen` / `video_gen` → ComfyUI | Avviare Comfy; video workflow dedicato |
| Ricerca web attendibile | `research` (SearXNG/ii) + `reach` | Installare SearXNG / Agent-Reach |
| Visione foto | `describe_vision` + vision-mcp fallback Ollama | Installare vision-mcp per OCR/video |
| Documenti | `doc_read` / `office_edit` | Installare Docling + OfficeCLI |
| Dispositivi | Fleet + `fleet_execute` + `mobile_ui` | mobile-mcp sul Mac Mini |

---

## 1) Creare immagini / video / codice + ricerca

### Codice (già in piano)

| Progetto | Stars / note | Ruolo JANIS | Priorità |
|----------|--------------|-------------|----------|
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Alto · grafo AST | Tool `code_*` | **P0** |
| Cursor Agent (già) | — | Implementazione codice | **P0** (attivo) |

### Generazione immagini / video

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **ComfyUI + comfy-cli** | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) · [comfy-cli](https://github.com/Comfy-Org/comfy-cli) | Locale su RTX 3080 Ti; API; agent `--json` | Setup pesante | **P0 locale** |
| **multimodal-mcp** | [rsmdt/multimodal-mcp](https://github.com/rsmdt/multimodal-mcp) | Un MCP: image+video+audio multi-provider | API a pagamento | **P1 cloud** |
| **artificer-mcp** | [bthurlow/artificer-mcp](https://github.com/bthurlow/artificer-mcp) | Gen + FFmpeg/ImageMagick post | Dipende Gemini/Veo keys | **P1** |
| **genai CLI** | [199-biotechnologies/genai](https://github.com/199-biotechnologies/genai) | CLI semplice Flux/Kling/Veo | Cloud fal/OpenAI | **P2** |
| **kie-ai-mcp** | [felores/kie-ai-mcp-server](https://github.com/felores/kie-ai-mcp-server) | Molti modelli media | Aggregatore third-party | **P2** |

**Raccomandazione:** ComfyUI locale come default (allinea LOCAL_FIRST); multimodal-mcp quando serve qualità cloud (Veo/Sora) con budget hard-stop.

### Ricerca attendibile (citazioni)

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **ii-researcher** | [Intelligent-Internet/ii-researcher](https://github.com/Intelligent-Internet/ii-researcher) | Deep search + report + MCP; PDF/YouTube | Stack completo | **P0** |
| **GPT Researcher + gptr-mcp** | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Maturo, citazioni | Spesso cloud LLM | **P1** |
| **SearXNG** | [searxng/searxng](https://github.com/searxng/searxng) | Meta-search self-host, no lock-in | Solo search, non report | **P0 infra** |
| **Firecrawl / Jina reader** | firecrawl, jina.ai | Estrazione pagine pulite | SaaS o self-host | **P1** |
| **deep-research-agent** | [deepakj111/deep-research-agent](https://github.com/deepakj111/deep-research-agent) | Web+arXiv+GitHub parallelo | Multi-key OpenAI/Anthropic | **P2** |
| **gigaxity-deep-research** | [yoloshii/gigaxity-deep-research](https://github.com/yoloshii/gigaxity-deep-research) | MCP + RRF + citazioni | Dipende OpenRouter | **P2** |

**Raccomandazione JANIS (no iscrizione):** pipeline nativa **SearXNG + fetch + Ollama** (`local_research.py` / tool `research`).  
ii-researcher / GPT-Researcher restano opzionali solo se accetti API search esterne (Tavily/SerpAPI).

### Internet / social (fetch piattaforme)

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **Agent-Reach** | [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | YT/X/Reddit/GH/RSS/Exa; doctor; skill Cursor; quasi free | Cookie/login su social; non report strutturato | **P0** |

**Raccomandazione:** Agent-Reach = occhi sul web (fetch); ii-researcher = sintesi con citazioni. Entrambi in W6h. Non far postare: solo lettura.

---

## 2) Vedere video/foto e leggere documenti

### Visione (foto / video)

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **JANIS describe_vision** | interno | Già Pocket + path | Video limitato | **base** |
| **vision-mcp (Pelican)** | [Pelican0126/vision-mcp](https://github.com/Pelican0126/vision-mcp) | OCR, UI, video, zoom agentic; backend OpenAI-compat → Ollama | Setup | **P0** |
| **vision-tool** | [farhanic017/vision-tool](https://github.com/farhanic017/vision-tool) | MCP+CLI; ffmpeg keyframes | Cloud opzionale | **P1** |
| **Whisper / faster-whisper** | già in brain STT | Audio → testo | Non video vision | **attivo** |

**Raccomandazione:** estendere `describe_vision` + MCP vision con **Ollama vision** (llava/qwen-vl) locale; ffmpeg frame sample per video.

### Documenti (PDF / Office / OCR)

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **Docling** (+ MCP) | [docling-project/docling](https://github.com/docling-project/docling) | PDF/DOCX/PPTX/HTML → Markdown; locale; MCP | RAM | **P0** |
| **OfficeCLI** | [iOfficeAI/OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) | Edit DOCX/XLSX/PPTX senza Office | Non PDF scanner | **P0** (già valutato) |
| **ocr-mcp** | [sandraschi/ocr-mcp](https://github.com/sandraschi/ocr-mcp) | OCR multi-engine + scanner WIA | Pesante | **P1** scanned |
| Marker / Unstructured | vari | PDF→MD | Alternativa a Docling | **P2** |

**Raccomandazione:** Docling per *leggere*; OfficeCLI per *creare/modificare* Office.

---

## 3) Usare tutti i dispositivi

### Già in JANIS

- Fleet WS: Mac Mini bridge  
- Pocket iOS: sensori, chat, vision upload  
- WSL brain + Windows tray/desktop  
- `mac_ssh`, `fleet_execute`, `win_vm`

### GitHub utili per estendere

| Progetto | Link | Pro | Contro | Priorità |
|----------|------|-----|--------|----------|
| **mobile-mcp** | [mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp) | iOS+Android real/sim, accessibilità | Setup WDA/adb | **P0** mobile UI |
| **agent-fleet (metahub)** | [metahub-tech/agent-fleet](https://github.com/metahub-tech/agent-fleet) | Win/Mac/Android/iOS come flotta MCP | Alpha | **P1** |
| **agent-device (Callstack)** | [callstack/agent-device](https://github.com/callstack/agent-device) | CLI agent-friendly iOS/Android | Focus testing | **P1** |
| **podium-mcp** | [hoainho/podium-mcp](https://github.com/hoainho/podium-mcp) | Un MCP 51 tool mobile+canvas | Complesso | **P2** |
| **Paperclip patterns** | [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Heartbeat/budget multi-agente | Non device driver | **P0 orch** (piano W6) |

**Raccomandazione:**  
1) Rafforzare fleet JANIS (hub + nodi)  
2) `mobile-mcp` sul Mac Mini per pilotare iPhone/iPad  
3) Android via adb sul Windows hub quando serve  
4) Orchestrator Paperclip-style per chi fa cosa sui dispositivi

---

## Stack target consigliato (priorità)

```
                    ┌─────────────────────────� sui dispositivi

---

## Stack target consigliato (priorità)

```
                    ┌─────────────────────────┐
                    │     JANIS brain ReAct    │
                    │  mcp_client + budget     │
                    └───────────┬─────────────┘
          ┌─────────────┬───────┼───────┬─────────────┐
          ▼             ▼       ▼       ▼             ▼
     DeusData      ComfyUI   Docling  vision-mcp   mobile-mcp
     (codice)      (+cloud    OfficeCLI ii-research  agent-fleet
                    media)              + SearXNG    + fleet WS
```

### Tier P0 (fare dopo W6a MCP client)

1. DeusData — codice  
2. Docling + OfficeCLI — documenti  
3. ComfyUI locale — immagini/video  
4. SearXNG + ii-researcher — ricerca citata  
5. vision-mcp (Ollama) — vedere foto/video  
6. mobile-mcp (Mac) — dispositivi iOS  
7. Orchestrator Paperclip-native — coordinamento

### Tier P1

- multimodal-mcp / artificer (cloud media qualità)  
- GPT Researcher  
- ocr-mcp  
- agent-fleet / agent-device  

### Tier P2 / evitare per ora

- Aggregatori media fragili (kie) senza bisogno  
- Stack deep-research multi-LLM costosi se ii-researcher basta  
- Podium se mobile-mcp è sufficiente  

---

## Allineamento budget e privacy

| Classe | Policy JANIS |
|--------|----------------|
| Locale (Comfy, Docling, Ollama vision, SearXNG, DeusData) | Default `LOCAL_FIRST` |
| Cloud media / research | Solo con `paid_mode` + hard-stop budget agente |
| Dispositivi | Solo nodi fleet autorizzati + token |

---

## Estensione piano integrazione

Aggiungere a W6 (dopo W6a):

| Sprint | Contenuto |
|--------|-----------|
| **W6b** | DeusData `code_*` |
| **W6f** | Docling MCP + OfficeCLI |
| **W6g** | ComfyUI tool `image_gen` / `video_gen` (locale) |
| **W6h** | SearXNG + research MCP → tool `research` |
| **W6i** | vision-mcp → potenzia `describe_vision` |
| **W6j** | mobile-mcp su Mac + registro fleet |

---

## Criterio di successo (capacità utente)

| Frase utente | Tool atteso |
|--------------|-------------|
| «Genera un’immagine di…» | ComfyUI / media MCP |
| «Fai un video corto di…» | Comfy video / Veo cloud |
| «Implementa X nel repo» | DeusData + Cursor |
| «Ricerca attendibile su Y con fonti» | `research` + citazioni |
| «Guarda questa foto/video» | vision + ffmpeg |
| «Leggi questo PDF / Excel» | Docling / OfficeCLI |
| «Apri l’app sull’iPhone e tap…» | mobile-mcp via Mac |
| «Esegui sul Mac / WSL» | fleet / mac_ssh |

---

## Nota metodo

Scan basata su ricerca web GitHub luglio 2026 + inventario del monorepo.  
Non è un dump di tutte le star: è una **shortlist actionable** per i tre obiettivi.  
Rivalutare trimestralmente con `tech_scout` JANIS.
