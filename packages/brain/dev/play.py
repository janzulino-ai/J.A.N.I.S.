"""
Entry point Play / F5 — avvia JANIS completa (backend + finestra Chromium).

Usato da Visual Studio (JANIS.pyproj StartupFile) e IDE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))

from desktop.launcher import run_app

if __name__ == "__main__":
    raise SystemExit(run_app(console=True, reload=False, window=True))
