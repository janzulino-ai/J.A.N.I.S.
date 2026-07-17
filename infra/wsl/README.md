# JANIS su WSL2 — brain local-only

## Stato attuale (funzionante)

| Componente | Dove |
|------------|------|
| **Brain** | WSL `:8001` |
| **Ollama** | Windows → WSL via `http://192.168.128.1:11434` |
| **Modello** | `gemma4:latest` |
| **venv** | `~/janis-venv` (virtualenv.pyz, no apt) |

## Avvio quotidiano

**Opzione consigliata — tray + autostart Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File "C:\APP IA\JANIS\infra\windows\install-tray-autostart.ps1"
```

Icona **J** nella system tray: avvia Ollama + brain WSL, apre HUD, toggle avvio con Windows.
Vedi `infra/windows/README.md`.

**Opzione one-shot (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File "C:\APP IA\JANIS\infra\wsl\start-janis-wsl.ps1"
```

**Manuale (due passi):**

**1. Ollama Windows** (una volta per sessione, o dopo reboot):

```powershell
powershell -File "C:\APP IA\JANIS\infra\wsl\start-ollama-windows.ps1"
```

**2. Brain WSL:**

```bash
bash ~/projects/J.A.N.I.S./infra/wsl/start-brain.sh
```

**3. Browser:** `http://localhost:8001/server`

## Setup iniziale (già fatto se hai ~/janis-venv)

```bash
bash ~/projects/J.A.N.I.S./infra/wsl/bootstrap-venv.sh
bash ~/projects/J.A.N.I.S./infra/wsl/configure-brain.sh
```

## Config zero costo

- `LOCAL_FIRST=true` · `CLOUD_LLM_ALLOWED=false`
- `runtime.json`: `cursor_code_enabled=false`
- Ollama Windows **non** in parallelo a Ollama WSL — usa bridge gateway

## Verifica

```bash
curl -s http://127.0.0.1:8001/api/status
bash ~/projects/J.A.N.I.S./infra/wsl/smoke-chat.sh
bash ~/projects/J.A.N.I.S./infra/wsl/smoke-w2.sh
bash ~/projects/J.A.N.I.S./infra/sidecars/verify-mode-a.sh   # Mode A sidecar (plan A3)
```

## LLM Lab — AI Auditor (W5)

Confronta risposta locale (Ollama) vs teacher (Cursor/OpenRouter) e salva audit JSON in `packages/brain/data/lab/audits/`.

```bash
curl -s -X POST http://127.0.0.1:8001/api/lab/audit \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Spiega cos'\''è un singleton in Python",
    "teacher_response": "Un singleton garantisce una sola istanza...",
    "student_response": "Il singleton è un pattern...",
    "student_model": "gemma4:latest"
  }'

curl -s http://127.0.0.1:8001/api/lab/audits?limit=5
curl -s http://127.0.0.1:8001/api/lab/audits/<audit_id>
```

Judge: `llm_router` (Cursor/OpenRouter se disponibili, altrimenti Ollama self-critique).

## Autostart Windows

- **Tray + Startup folder:** `infra/windows/install-tray-autostart.ps1`
- **Task Scheduler WSL:** `infra/windows/install-autostart-wsl.ps1`
- **One-shot:** `infra/wsl/start-janis-wsl.ps1`

## Note

- `.env` e script `.sh`: se errori `$'\r'`, esegui `sed -i 's/\r$//' file`
- `python3-venv` apt opzionale — usiamo `virtualenv.pyz`
- Ollama nativo WSL (opzionale futuro): `bash infra/wsl/install-ollama-user.sh`
