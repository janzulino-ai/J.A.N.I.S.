# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
J.A.N.I.S. is a directory-based monorepo. The only component that builds/runs/tests on this
Linux VM is the FastAPI "brain" at `packages/brain/` (it also serves the web/kiosk UIs). The
iOS app (`apps/pocket/`) and Windows/.NET app (`apps/janis-windows/`) require macOS/Xcode and
Windows and cannot be built here.

Standard commands live in `packages/brain/README.md` and `packages/brain/.github/workflows/ci.yml`.

### Environment (already applied by the update script + VM snapshot)
- Python venv lives at `packages/brain/.venv`. Activate with `. packages/brain/.venv/bin/activate`
  or call `packages/brain/.venv/bin/python` directly.
- `packages/brain/.env` is **required** and is git-ignored (it persists only in the VM snapshot).
  It was created from `.env.example` with the server-specific paths retargeted to this repo:
  `JANIS_WORKSPACE=/workspace`, `JANIS_PROJECT_DIR=/workspace/packages/brain`,
  `JANIS_MONOREPO_ROOT=/workspace`. Without these overrides the app defaults to `/home/janis`
  and crashes/tests fail with `PermissionError: [Errno 13] ... '/home/janis'`. If `.env` is ever
  missing, recreate it from `.env.example` with those three paths retargeted to `/workspace`.

### Run (dev)
From `packages/brain` with the venv active: `python run.py` → serves on `http://0.0.0.0:8001`
(web IDE at `/`, kiosk HUD at `/server`, setup wizard at `/setup`). There is no `--reload`; a
no-cache middleware handles static freshness. There is no frontend build step and no lint step.

### Test
Run from `packages/brain` as `python -m pytest tests/` — use the `python -m` form. Bare `pytest`
fails with `ModuleNotFoundError: No module named 'backend'` because the package root isn't on
`sys.path`; `python -m` adds the current dir. Expect one pre-existing failure on Linux:
`tests/test_security.py::test_path_outside_workspace` is Windows-only (it passes a
`C:\...` path that is only "outside the workspace" on Windows). CI runs on `windows-latest`, so it
passes there. Everything else passes (~95 passed, 1 skipped).

### Optional: local LLM chat (Ollama)
The server boots and the test suite passes without Ollama; chat just won't produce replies. For a
live end-to-end chat:
- Install **Ollama 0.6.8** (`curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION=0.6.8 sh`).
  Newer Ollama releases **segfault** in this microVM during model warmup (AMX/AVX-512 CPU kernels),
  so pin 0.6.8.
- systemd is not available here — start it manually: `ollama serve` (e.g. in a tmux session), then
  `ollama pull llama3.2:3b`.
- Point the brain at that model: set `OLLAMA_MODEL=llama3.2:3b` in `.env`, and select the local
  provider via `curl -X POST localhost:8001/api/runtime -d '{"paid_mode":false,"reasoning_provider":"ollama"}'`
  (default `data/runtime.json` uses PRO/`cursor`, which needs a `CURSOR_API_KEY`). CPU inference of
  a chat turn takes a few to ~30 seconds.
