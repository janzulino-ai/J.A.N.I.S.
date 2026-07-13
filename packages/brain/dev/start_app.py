"""Entry avvio app — senza console (usa desktop.launcher)."""
from desktop.launcher import run_app

if __name__ == "__main__":
    raise SystemExit(run_app(silent=True, reload=False, window=True))
