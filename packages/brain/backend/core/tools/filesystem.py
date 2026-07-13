import os

from backend.config import settings
from backend.core.security import validate_path
from backend.core.tools.registry import register


@register("read_file")
async def read_file(args: dict) -> str:
    path = args.get("path", "").strip()
    if not path:
        return "Errore: 'path' obbligatorio."
    try:
        resolved = validate_path(path, must_exist=True)
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 12000:
            return content[:12000] + "\n\n[... troncato ...]"
        return content
    except Exception as e:
        return f"Errore lettura: {e}"


@register("write_file")
async def write_file(args: dict) -> str:
    path = args.get("path", "").strip()
    content = args.get("content", "")
    if not path:
        return "Errore: 'path' obbligatorio."
    try:
        resolved = validate_path(path)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File scritto: {resolved} ({len(content)} caratteri)"
    except Exception as e:
        return f"Errore scrittura: {e}"


@register("list_dir")
async def list_dir(args: dict) -> str:
    path = args.get("path", settings.JANIS_WORKSPACE).strip()
    try:
        resolved = validate_path(path, must_exist=True)
        entries = os.listdir(resolved)
        lines = [f"Directory: {resolved}", ""]
        for name in sorted(entries)[:200]:
            full = os.path.join(resolved, name)
            kind = "DIR" if os.path.isdir(full) else "FILE"
            lines.append(f"  [{kind}] {name}")
        if len(entries) > 200:
            lines.append(f"  ... e altri {len(entries) - 200} elementi")
        return "\n".join(lines)
    except Exception as e:
        return f"Errore list_dir: {e}"
