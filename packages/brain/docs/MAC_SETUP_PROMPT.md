# Prompt Cursor — parità JANIS su Mac

Copia tutto il blocco **PROMPT** qui sotto in Cursor Agent (o CLI) con `cwd` = root repo JANIS.

---

## Prima di lanciare (checklist Mac)

- [ ] `git pull` — repo allineato a Windows/GitHub
- [ ] Python 3.12 + `pip install -r requirements.txt`
- [ ] Ollama installato e in esecuzione (`ollama list`)
- [ ] Cursor collegato a GitHub, stesso repo JANIS
- [ ] Copia `.env.example` → `.env` e adatta path Mac (vedi sotto)
- [ ] `CURSOR_API_KEY` in `.env` se usi PRO / self_develop

---

## PROMPT (copia da qui)

```
Sei Cursor Agent sul Mac Mini. Obiettivo: parità funzionale JANIS rispetto a Windows, senza rompere il codice Windows esistente.

Repo: root JANIS (FastAPI :8001, frontend static, pywebview desktop, Ollama brain, tool registry, PRO/Cursor SDK).

## Regole
- Usa sys.platform / pathlib — non rimuovere codice Windows, estendi con branch darwin dove serve.
- Diff minimi, stile codebase esistente.
- Test: `python -c "from backend.main import app"` e avvio `uvicorn backend.main:app --host 127.0.0.1 --port 8001`.
- Documenta in docs/MAC.md cosa hai fatto e come avviare.
- Commit su branch `mac-parity` (non main) con messaggi chiari.

## .env Mac (esempio — adatta username)
JANIS_WORKSPACE=/Users/TUO/Projects
JANIS_PROJECT_DIR=/Users/TUO/path/to/JANIS
OLLAMA_BASE_URL=http://127.0.0.1:11434
HOST=0.0.0.0
PORT=8001

## Task 1 — Script dev macOS
Crea equivalenti di dev/*.ps1:
- dev/run-debug.sh — stop + launcher con log in terminale, chmod +x
- dev/stop-janis.sh — termina uvicorn/launcher JANIS, libera porta 8001
- dev/start_backend.py già esiste — verifica PYTHONPATH

## Task 2 — Backend cross-platform
- backend/core/open_url.py — su darwin usare `open` / webbrowser per browser di sistema
- backend/core/security.py — validate_path: supporto multi-root futuro OK, almeno workspace Mac
- backend/desktop/process_util.py (se usato) — kill process su macOS (pgrep/pkill o psutil)
- Verifica backend/main.py parte su Mac

## Task 3 — Desktop shell Mac
- desktop/launcher.py — su darwin: niente CREATE_NO_WINDOW, cwd corretto, pywebview gui edgechromium/cocoa
- desktop/shell.py — JanisShellApi.open_url su Mac
- desktop/overlay.py — su Mac: skip Win32 overlay o no-op documentato (finestra normale OK)
- Entry: `python -m desktop.launcher --console` deve aprire UI http://127.0.0.1:8001

## Task 4 — Tool terminal/filesystem su Mac
- backend/core/tools/terminal.py — shell /bin/zsh, path Unix
- Test: system_info riporta macOS

## Task 5 — Fleet (preparazione, opzionale se tempo)
Leggi docs/FLEET_PROJECT.md. Crea stub minimo:
- bridge/client.py — WS client verso hub Windows (device_id=mac-mini, hello, heartbeat)
- config/fleet.yaml.example con host Windows e nome nodo mac-mini
Non implementare tutta la flotta — solo client connect + doc.

## Task 6 — Docs
- docs/MAC.md — prerequisiti, avvio, permessi (Full Disk Access se serve indicizzazione futura), differenze vs Windows
- Aggiorna .env.example con commenti path Mac

## Non fare
- Non refactor massivo frontend
- Non rimuovere PowerShell scripts Windows
- Non committare .env con secrets

## Output atteso
1. JANIS avviabile su Mac con ./dev/run-debug.sh
2. Browser di sistema apre URL (open_browser tool)
3. Chat + PRO + Cursor SDK funzionanti come su Windows
4. docs/MAC.md completo
5. Branch mac-parity pronto per push/PR

Inizia leggendo: docs/DEV.md, desktop/launcher.py, backend/core/open_url.py, dev/run-debug.ps1 (come riferimento Windows).
Procedi task per task; a fine ogni task elenca cosa hai verificato.
```

---

## Comando terminale Mac (alternativa)

Dalla root repo, se hai Cursor CLI:

```bash
cd ~/path/to/JANIS
git pull
cursor agent "$(sed -n '/^```$/,/^```$/p' docs/MAC_SETUP_PROMPT.md | head -n -1 | tail -n +2)"
```

Oppure apri `docs/MAC_SETUP_PROMPT.md` in Cursor e incolla solo il blocco PROMPT in Agent.

---

## Dopo Cursor — sync

```bash
git add -A && git commit -m "mac: parità dev shell e backend darwin"
git push origin mac-parity
```

Su Windows: `git pull` e continui da hub.

---

## Hub Windows (IP per fleet, quando pronto)

In `config/fleet.yaml` sul Mac:

```yaml
hub_url: ws://IP-WINDOWS:8001/ws/fleet-node
node_name: mac-mini
token: STESSO_TOKEN_DI_WINDOWS
```
