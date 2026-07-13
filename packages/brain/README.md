# JANIS



**J**ust **A**nalyzing **N**etworks, **I**ntelligence, **C**ommunication & **E**xecution



Assistente AI personale per Windows — backend FastAPI, UI web tipo IDE, Ollama locale, second brain a grafo, agenti modulari.



## Requisiti



- Windows 11

- Python 3.12

- [Ollama](https://ollama.com/) con modelli locali (es. `gemma4`, `qwen3.6`)

- WebView2 (incluso in Windows 11)



## Avvio rapido



```powershell

cd "C:\APP IA\JANIS"

copy .env.example .env

pip install -r requirements.txt

.\start-janis-window.ps1

```



Browser: http://127.0.0.1:8001/?mode=browser



## Visual Studio — F5 debug



1. Apri `JANIS.sln` in Visual Studio

2. Seleziona configurazione **Debug**

3. Premi **F5** — avvia `dev/start_backend.py` (hot-reload + browser automatico)

4. Per desktop completo: esegui `dev/start_desktop.py` o `start-janis-window.ps1`



Setup guidato: http://127.0.0.1:8001/setup



## Struttura



```

backend/     API, brain ReAct, tools, memoria, sicurezza

frontend/    UI IDE, Three.js second brain, window manager, pagine sidebar

desktop/     Shell pywebview (overlay / finestra)

scripts/     Installazione, build, backup

build/       PyInstaller spec

tests/       pytest

data/        Memoria e log locali (non in git)

docs/        Architettura, Linux phase 2

```



## Roadmap (stato)



| # | Feature | Stato |

|---|---------|-------|

| R1 | Sidebar Lavori / Progetti / Impostazioni | ✓ |

| R2 | Click cervello → dettaglio memoria | ✓ |

| R3 | Pannello Cursor con streaming WS | ✓ |

| R4 | LLM router Ollama + OpenRouter | ✓ |

| R5 | Pannello WhatsApp (stub) | ✓ |

| R6 | Window manager stabilizzato | ✓ |

| R7 | TTS con coda e controlli | ✓ |

| R8 | Memoria: dedup, tag, paginazione, search | ✓ |

| R9 | PyInstaller `JANIS.exe` | ✓ spec + script |

| R10 | First-run wizard | ✓ modal + `/setup` |

| R11 | Security hardening workspace/comandi | ✓ |

| R12 | Test pytest + CI GitHub Actions | ✓ |

| R13 | Documentazione | ✓ |

| R14 | Backup memoria + export API | ✓ |

| R15 | Linux phase 2 | placeholder `docs/LINUX.md` |



## Configurazione



- `OLLAMA_*` — modello locale

- `LLM_PROVIDER` — `ollama` | `openrouter` | `auto`

- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` — fallback cloud (opzionale)

- `CURSOR_API_KEY` — agenti Cursor SDK (opzionale)

- `JANIS_WORKSPACE` / `JANIS_PROJECT_DIR` — percorsi operativi

- `JANIS_TTS_*` — voce edge-tts



## Test



```powershell

python -c "from backend.main import app; print(app.title)"

pytest tests/ -v

```



## Build eseguibile



```powershell

.\scripts\build-exe.ps1

# Output: dist\JANIS.exe

```



## Backup memoria



```powershell

.\scripts\backup-memory.ps1

# GET /api/memory/export — download JSON

```



## Licenza



Privato — uso personale.

