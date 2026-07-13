"""Strumenti scansione cartelle autorizzate (film, media)."""
from __future__ import annotations

import json

from backend.core.folder_index import (
    default_scan_path,
    get_index_stats,
    run_scan,
    search_index,
)
from backend.core.tools.registry import register


@register("scan_folder")
async def scan_folder(args: dict) -> str:
    category = (args.get("category") or "movies").strip().lower()
    path = (args.get("path") or "").strip() or None
    try:
        result = run_scan(path=path, category=category)
        size_gb = result["total_size_bytes"] / (1024 ** 3)
        return (
            f"Scansione completata ({category}): {result['count']} file in {result['path']}\n"
            f"Dimensione totale: {size_gb:.2f} GB\n"
            f"Memorie aggiornate: {result['memories_updated']}\n"
            f"Data: {result['scanned_at'][:19]}"
        )
    except PermissionError as e:
        return f"Errore permessi: {e}. Aggiungi la cartella a JANIS_SCAN_ROOTS in .env."
    except FileNotFoundError as e:
        return f"Errore: {e}"
    except NotADirectoryError as e:
        return f"Errore: {e}"
    except Exception as e:
        return f"Errore scansione: {e}"


@register("search_folder_index")
async def search_folder_index(args: dict) -> str:
    query = (args.get("query") or "").strip()
    category = (args.get("category") or "movies").strip().lower()
    limit = int(args.get("limit") or 15)

    stats = get_index_stats(category)
    if stats["count"] == 0:
        default_path = default_scan_path(category)
        return (
            f"Indice {category} vuoto. Esegui scan_folder "
            f"(path opzionale, default: {default_path})."
        )

    matches = search_index(query, category, limit=limit)
    if not matches:
        return f"Nessun risultato per '{query}' nell'indice {category} ({stats['count']} file totali)."

    lines = [
        f"Indice {category}: {stats['count']} file (scansione {str(stats['scanned_at'])[:19]})",
        "",
    ]
    for m in matches:
        year = m.get("year") or "?"
        size_mb = m.get("size", 0) / (1024 ** 2)
        lines.append(f"- {m['name']} [{year}] ({size_mb:.0f} MB) — {m['path']}")
    return "\n".join(lines)


@register("folder_index_status")
async def folder_index_status(args: dict) -> str:
    category = (args.get("category") or "movies").strip().lower()
    stats = get_index_stats(category)
    return json.dumps(stats, ensure_ascii=False, indent=2)


@register("add_knowledge_folder")
async def add_knowledge_folder(args: dict) -> str:
    """
    Aggiunge una cartella da conoscere e la fa apprendere con Ollama (neuroni/memoria).
    args: path (obbligatorio), learn (bool, default true)
    """
    path = (args.get("path") or "").strip()
    learn = args.get("learn", True)
    if not path:
        return (
            "Errore: indica il percorso completo, es. D:\\Film oppure "
            "C:\\Users\\nome\\Videos"
        )
    try:
        from backend.core.folder_knowledge import add_knowledge_folder_path, enrich_folder

        resolved = add_knowledge_folder_path(path)
    except FileNotFoundError as e:
        return f"Errore: {e}. Verifica che la cartella esista."
    except PermissionError as e:
        return f"Errore: {e}"
    except Exception as e:
        return f"Errore aggiunta cartella: {e}"

    if learn is False or str(learn).lower() in ("0", "false", "no"):
        return f"Cartella registrata: {resolved}. Apprendimento non avviato (learn=false)."

    try:
        result = await enrich_folder(resolved)
    except Exception as e:
        return f"Cartella registrata ({resolved}) ma apprendimento Ollama fallito: {e}"

    return (
        f"Ho appreso la cartella: {resolved}\n"
        f"Area: {result.get('area', '—')}\n"
        f"Cluster tematici: {result.get('clusters', 0)}\n"
        f"Memorie/neuroni creati: {result.get('memories_created', 0)}\n"
        f"File analizzati: {result.get('file_count', 0)}"
    )


@register("list_knowledge_folders")
async def list_knowledge_folders(args: dict) -> str:
    """Elenco cartelle conosciute e stato apprendimento."""
    from backend.core.folder_knowledge import get_knowledge_status

    st = get_knowledge_status()
    lines = [
        f"Cartelle autorizzate ({len(st.get('scan_roots') or [])}):",
    ]
    for p in st.get("scan_roots") or []:
        meta = (st.get("folders") or {}).get(p) or {}
        area = meta.get("area") or "—"
        when = (meta.get("enriched_at") or "non ancora appresa")[:19]
        lines.append(f"- {p} [{area}] aggiornata: {when}")
    if st.get("last_enriched"):
        lines.append(f"\nUltimo apprendimento globale: {st['last_enriched'][:19]}")
    return "\n".join(lines)
