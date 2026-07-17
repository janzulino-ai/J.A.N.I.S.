"""Fallback nativi JANIS quando i sidecar MCP non sono disponibili."""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

# Estensioni tipiche codice
_CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".m",
    ".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".sql",
    ".html", ".css", ".vue", ".svelte",
}

_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", "target", "bin", "obj", ".tox", ".mypy_cache", ".pytest_cache",
    "EBWebView",
}


def _root(path: str | None, default: str) -> Path:
    p = Path(path or default).expanduser()
    return p if p.exists() else Path(default)


async def native_code_search(query: str, *, root: str | None = None, limit: int = 40) -> str:
    """Cerca nel workspace con ripgrep se presente, altrimenti pathlib."""
    from backend.config import settings

    base = _root(root, settings.JANIS_WORKSPACE or settings.JANIS_PROJECT_DIR)
    q = query.strip()
    if not q:
        return "query obbligatoria"
    if not base.exists():
        return f"Workspace non trovato: {base}"

    rg = shutil.which("rg") or shutil.which("ripgrep")
    if rg:
        try:
            proc = await asyncio.create_subprocess_exec(
                rg,
                "-n",
                "--no-heading",
                "--color",
                "never",
                "-S",
                "-m",
                str(max(1, min(limit, 80))),
                q,
                str(base),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45.0)
            out = (stdout or b"").decode("utf-8", errors="replace").strip()
            err = (stderr or b"").decode("utf-8", errors="replace").strip()
            if proc.returncode in (0, 1) and out:
                lines = out.splitlines()[:limit]
                header = f"[native:ripgrep] root={base} query={q!r} hits={len(lines)}\n"
                return header + "\n".join(lines)
            if proc.returncode not in (0, 1) and err:
                # fall through to pathlib
                pass
            elif proc.returncode == 1:
                return f"[native:ripgrep] nessun match per {q!r} in {base}"
        except Exception:
            pass

    return await asyncio.to_thread(_pathlib_search, base, q, limit)


def _pathlib_search(base: Path, query: str, limit: int) -> str:
    needle = query.lower()
    hits: list[str] = []
    for path in base.rglob("*"):
        if len(hits) >= limit:
            break
        try:
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in _CODE_EXT and path.suffix:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                rel = path.relative_to(base) if path.is_relative_to(base) else path
                hits.append(f"{rel}:{i}:{line.strip()[:200]}")
                if len(hits) >= limit:
                    break
    header = f"[native:pathlib] root={base} query={query!r} hits={len(hits)}\n"
    if not hits:
        return header + "nessun match"
    return header + "\n".join(hits)


def native_read_text(path: Path, *, max_chars: int = 12000) -> str | None:
    """Legge testo grezzo per estensioni note."""
    if path.suffix.lower() in (".txt", ".md", ".csv", ".json", ".log", ".yml", ".yaml", ".toml", ".py", ".js", ".ts"):
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError:
            return None
    return None


def native_read_pdf(path: Path, *, max_chars: int = 12000) -> str | None:
    """Estrae testo PDF senza Docling — pypdf se installato, altrimenti heuristica streams."""
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:40]:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
            if sum(len(p) for p in parts) >= max_chars:
                break
        text = "\n\n".join(parts).strip()
        if text:
            return f"[native:pypdf] {path.name}\n" + text[:max_chars]
    except Exception:
        pass

    try:
        raw = path.read_bytes()
    except OSError:
        return None
    # Heuristica: stringhe leggibili tra parentesi tipiche PDF (Tj / TJ)
    chunks = re.findall(rb"\((?:\\.|[^\\)]){3,}\)[\s]*Tj", raw[:2_000_000])
    texts: list[str] = []
    for c in chunks:
        inner = c[1 : c.rfind(b")")]
        try:
            s = inner.decode("latin-1", errors="ignore")
        except Exception:
            continue
        s = s.replace("\\n", "\n").replace("\\(", "(").replace("\\)", ")")
        if sum(ch.isalnum() for ch in s) >= 3:
            texts.append(s)
    joined = " ".join(texts)
    joined = re.sub(r"\s+", " ", joined).strip()
    if len(joined) < 40:
        return None
    return f"[native:pdf-heuristic] {path.name}\n" + joined[:max_chars]


async def native_doc_read(path: str, *, max_chars: int = 12000) -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        return f"File non trovato: {path}"
    text = native_read_text(p, max_chars=max_chars)
    if text is not None:
        return f"[native:text] {p.name}\n" + text
    if p.suffix.lower() == ".pdf":
        pdf = await asyncio.to_thread(native_read_pdf, p, max_chars=max_chars)
        if pdf:
            return pdf
        return (
            f"PDF non leggibile in modalità nativa: {path}\n"
            "Installa Docling MCP (docling-mcp-server) o `pip install pypdf`."
        )
    return (
        f"Formato non supportato dal fallback nativo ({p.suffix}).\n"
        "Serve Docling MCP per Office/PDF complessi."
    )
