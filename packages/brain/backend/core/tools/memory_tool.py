import json
import os
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

import httpx

from backend.config import settings
from backend.core.tools.registry import register

_MEMORY_FILE = None  # legacy — use _memory_file()


def _memory_file() -> str:
    return os.path.join(settings.MEMORY_DIR, "long_term.json")


def _stats_file() -> str:
    return os.path.join(settings.MEMORY_DIR, "knowledge_stats.json")


def _normalize_text(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    return t


def _normalize_tags(tags) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,;]", tags) if t.strip()]
    out = []
    seen = set()
    for t in tags:
        tag = re.sub(r"\s+", "-", str(t).strip().lower())
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _load() -> list[dict]:
    os.makedirs(settings.MEMORY_DIR, exist_ok=True)
    if not os.path.exists(_memory_file()):
        return []
    try:
        with open(_memory_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    os.makedirs(settings.MEMORY_DIR, exist_ok=True)
    with open(_memory_file(), "w", encoding="utf-8") as f:
        json.dump(entries[-500:], f, ensure_ascii=False, indent=2)


def _load_stats() -> dict:
    os.makedirs(settings.MEMORY_DIR, exist_ok=True)
    if not os.path.exists(_stats_file()):
        return {"user_messages": 0, "janis_interactions": 0}
    try:
        with open(_stats_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "user_messages": int(data.get("user_messages", 0)),
            "janis_interactions": int(data.get("janis_interactions", 0)),
        }
    except Exception:
        return {"user_messages": 0, "janis_interactions": 0}


def _save_stats(stats: dict) -> None:
    os.makedirs(settings.MEMORY_DIR, exist_ok=True)
    with open(_stats_file(), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


def increment_user_message() -> None:
    stats = _load_stats()
    stats["user_messages"] += 1
    _save_stats(stats)


def increment_janis_interaction() -> None:
    stats = _load_stats()
    stats["janis_interactions"] += 1
    _save_stats(stats)


def get_knowledge_stats() -> dict:
    entries = _load()
    stats = _load_stats()
    user_mem = sum(1 for e in entries if e.get("source", "user") != "janis")
    janis_mem = sum(1 for e in entries if e.get("source") == "janis")
    count = len(entries)

    user_level = min(100, max(3, user_mem * 5 + stats["user_messages"] * 2 + 3))
    janis_level = min(
        100, max(3, janis_mem * 5 + stats["janis_interactions"] * 2 + 3),
    )
    level = max(user_level, janis_level)

    return {
        "memories": count,
        "level": level,
        "count": count,
        "user_level": user_level,
        "janis_level": janis_level,
        "user_memories": user_mem,
        "janis_memories": janis_mem,
    }


def _find_duplicate(entries: list[dict], text: str, threshold: float = 0.88) -> dict | None:
    norm = _normalize_text(text)
    for e in reversed(entries):
        if _similarity(norm, _normalize_text(e.get("text", ""))) >= threshold:
            return e
    return None


async def _embed_query(query: str) -> list[float] | None:
    model = (settings.OLLAMA_EMBED_MODEL or "").strip()
    if not model:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
                json={"model": model, "prompt": query},
            )
            if r.status_code != 200:
                return None
            return r.json().get("embedding")
    except Exception:
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _semantic_search(entries: list[dict], query: str, limit: int = 10) -> list[dict]:
    q_emb = await _embed_query(query)
    if not q_emb:
        return []
    scored = []
    for e in entries:
        emb = e.get("embedding")
        if not emb:
            emb = await _embed_query(e.get("text", "")[:500])
            if emb:
                e["embedding"] = emb
        if emb:
            scored.append((e, _cosine(q_emb, emb)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [e for e, s in scored[:limit] if s > 0.35]


def get_memory_by_id(memory_id: str) -> dict | None:
    for e in _load():
        if e.get("id") == memory_id:
            return e
    return None


def count_memories() -> int:
    return len(_load())


def list_memories_paginated(page: int, page_size: int) -> list[dict]:
    entries = _load()
    entries.reverse()
    start = (page - 1) * page_size
    return entries[start : start + page_size]


def export_all() -> list[dict]:
    return _load()


def export_memories() -> dict:
    return {"exported_at": datetime.now().isoformat(), "memories": export_all()}


def list_memories(page: int = 1, limit: int = 20) -> dict:
    total = count_memories()
    items = list_memories_paginated(page, limit)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


MEMORY_QUERY_KEYWORDS = (
    "memoria", "memorie", "conoscenz", "imparato",
    "caricat", "neuroni", "vault", "long_term", "long term",
    "persisten", "cosa sai", "cosa ricordi", "long-term",
    "progetti mac", "scan mac",
)

# Intento di SCRIVERE regole / remember — non è una domanda di lettura
MEMORY_WRITE_PHRASES = (
    "creare regole", "creare delle regole", "salvare regole", "nuova regola",
    "nuove regole", "aggiungi regola", "imposta regola", "voglio ricordare",
    "puoi ricordare", "che tu possa ricordare", "devi ricordare",
    "memorizza", "salva in memoria", "salva questa regola", "salva regola",
    "agire sulle tue risposte", "dalle tue risposte", "dalla tua risposta",
    "ricorda che", "ricorda:", "remember:",
)

MEMORY_READ_PHRASES = (
    "cosa ricordi", "cosa sai", "cosa hai in memoria", "cosa hai imparato",
    "dimmi cosa ricordi", "dimmi la memoria", "leggi memoria", "leggi la memoria",
    "mostra memorie", "mostra la memoria", "stato memoria", "memory status",
    "quante memorie", "quanti ricordi", "hai memoria", "vedi la memoria",
    "quali regole", "regole che ricordi", "regole attive", "protocollo",
    "parlato con cursor", "parlato con te cursor", "hai parlato con cursor",
)

RULE_TAGS = frozenset({"regola", "regole", "protocollo", "preferenza", "preference", "prefs", "style", "tono"})

_FALSE_MEMORY_DENIAL_PHRASES = (
    "non vedo nulla",
    "non ci sono nuovi dati",
    "non ho nuove conoscenze",
    "memoria è vuota",
    "memoria e vuota",
    "devi caricare",
    "devi fornirmi",
    "forniscimi il contenuto",
    "forniscimi la prova",
    "usa `remember`",
    "usa remember",
    "usa `recall`",
    "usa recall",
    "usa write_file",
    "non ho dati",
    "non ho nulla in memoria",
    "limitazione architetturale",
    "non è un bug di codice",
    "non c'è nulla da riparare",
    "non c'e nulla da riparare",
    "devi usare recall",
    "sei tu che devi",
)


def is_remember_request(user_text: str) -> bool:
    """Richiesta esplicita di scrivere in memoria — non confondere con domanda."""
    lower = (user_text or "").lower().strip()
    if lower.startswith("ricorda ") or lower.startswith("remember "):
        return True
    if lower.startswith("ricorda:") or lower.startswith("remember:"):
        return True
    return False


def is_memory_write_intent(user_text: str) -> bool:
    """Utente vuole creare/salvare regole o fatti — non chiede un riepilogo."""
    if is_remember_request(user_text):
        return True
    lower = (user_text or "").lower()
    if any(p in lower for p in MEMORY_WRITE_PHRASES):
        return True
    if "regol" in lower and any(w in lower for w in ("crea", "salva", "scriv", "voglio", "dammi", "imposta", "aggiung")):
        return True
    if "ricord" in lower and any(w in lower for w in ("voglio", "puoi", "devi", "che tu", "creare", "salva")):
        return True
    return False


def is_memory_status_request(user_text: str) -> bool:
    """Richiesta esplicita del dump completo (debug / stato tecnico)."""
    lower = (user_text or "").lower()
    return any(p in lower for p in (
        "stato memoria", "memory status", "memory_status", "quante memorie",
        "quanti ricordi", "dump memoria", "riepilogo completo",
    ))


def is_memory_query(user_text: str) -> bool:
    """Domanda di LETTURA memoria — esclude intenti di scrittura regole."""
    if is_memory_write_intent(user_text):
        return False
    lower = (user_text or "").lower()
    if any(p in lower for p in MEMORY_READ_PHRASES):
        return True
    if "memoria" in lower and any(
        w in lower for w in (
            "cosa", "dimmi", "mostra", "leggi", "quante", "quanti", "hai", "vedi", "stato",
            "persisten", "caricat", "aggiunt", "nuov",
        )
    ):
        return True
    if "conoscen" in lower and any(
        w in lower for w in ("hai", "nuov", "parla", "dimmi", "vedi", "caricat", "aggiunt", "memoria")
    ):
        return True
    if "cursor" in lower and any(
        w in lower for w in ("parlato", "parlare", "interag", "conversaz", "parlato con cursor")
    ):
        return True
    return False


def parse_inline_remember(user_text: str) -> str | None:
    """Estrae testo da «ricorda: …» o «ricorda che …»."""
    text = (user_text or "").strip()
    for prefix in ("ricorda:", "remember:", "ricorda che ", "remember that "):
        if text.lower().startswith(prefix):
            body = text[len(prefix):].strip()
            return body if len(body) >= 3 else None
    if is_remember_request(text):
        body = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        return body if len(body) >= 3 else None
    return None


def get_rule_memories(limit: int = 10) -> list[dict]:
    """Regole e protocolli utente — tag o testo esplicito."""
    out: list[dict] = []
    for entry in reversed(_load()):
        tags = {str(t).lower() for t in (entry.get("tags") or [])}
        txt = (entry.get("text") or "").lower()
        if tags & RULE_TAGS or "protocollo" in txt or txt.startswith("regola"):
            out.append(entry)
            if len(out) >= limit:
                break
    return out


def build_memory_read_response(user_text: str) -> str:
    """Risposta umana e contestuale — non dump robotico fisso."""
    entries = _load()
    lower = (user_text or "").lower()
    stats = get_knowledge_stats()

    if not entries:
        return (
            "Non ho ancora nulla in memoria permanente. "
            "Puoi dirmi «ricorda: …» oppure chiedermi di scansionare Mac o cartelle."
        )

    cursor_question = "cursor" in lower and any(
        w in lower for w in ("parlato", "parlare", "interag", "conversaz")
    )
    if cursor_question:
        from backend.core.cursor_memory import get_cursor_bridge_context
        bridge = get_cursor_bridge_context()
        if bridge:
            return f"Sì, ho sessioni Cursor↔JANIS in memoria.\n\n{bridge[:1200]}"
        return "Non ho ancora log di sessioni Cursor in memoria."

    rules_question = any(w in lower for w in ("regol", "protocollo", "preferenz", "tono", "stile"))

    if rules_question:
        rules = get_rule_memories()
        if not rules:
            return "Non ho ancora regole o protocolli salvati. Scrivi «ricorda: …» per aggiungerne una."
        lines = ["Ecco le regole e preferenze che applico:"]
        for i, entry in enumerate(rules[:8], 1):
            txt = entry.get("text", "").replace("\n", " ").strip()
            lines.append(f"{i}. {txt[:280]}")
        if len(rules) > 8:
            lines.append(f"… e altre {len(rules) - 8}.")
        return "\n".join(lines)

    if is_memory_status_request(user_text):
        mac_count = count_memories_by_tags(["knowledge-mac"])
        lines = [
            f"Memorie totali: {stats['memories']} "
            f"(utente: {stats['user_memories']}, JANIS: {stats['janis_memories']})",
            f"Conoscenza Mac: {mac_count} voci",
        ]
        for entry in entries[-3:]:
            lines.append(f"• [{entry.get('timestamp', '')[:10]}] {entry.get('text', '')[:120]}")
        return "\n".join(lines)

    mac_question = any(k in lower for k in ("mac", "fleet", "ssh", "mini", "progetti"))
    if mac_question:
        mac_entries = [
            e for e in get_memories_by_tags(["knowledge-mac"], limit=8)
            if not (e.get("text") or "").startswith("[Mac Fleet]")
        ]
        lines = [f"Conosco {count_memories_by_tags(['knowledge-mac'])} voci Mac in memoria."]
        fleet = get_memories_by_tags(["mac-fleet"], limit=1)
        if fleet:
            lines.append(f"\n{fleet[0].get('text', '')[:300]}")
        if mac_entries:
            lines.append("\nAlcuni progetti:")
            for e in mac_entries[:5]:
                lines.append(f"• {e.get('text', '')[:160]}")
        return "\n".join(lines)

    # Domanda generica «cosa ricordi» — sintesi breve
    rules = get_rule_memories()
    lines = [
        f"Ho {stats['memories']} memorie persistenti "
        f"({stats['user_memories']} tue, {stats['janis_memories']} mie)."
    ]
    if rules:
        lines.append(f"\nRegole attive ({len(rules)}):")
        for entry in rules[:3]:
            lines.append(f"• {entry.get('text', '')[:160]}")
    mac_n = count_memories_by_tags(["knowledge-mac"])
    if mac_n:
        lines.append(f"\nMac: {mac_n} progetti indicizzati.")
    recent_user = [e for e in reversed(entries) if e.get("source") != "janis"][:2]
    if recent_user:
        lines.append("\nUltimo da te:")
        for e in recent_user:
            lines.append(f"• {e.get('text', '')[:140]}")
    lines.append("\nChiedi dettagli su regole, Mac o Cursor — oppure «stato memoria» per il riepilogo completo.")
    return "\n".join(lines)


def build_memory_write_response(user_text: str) -> str:
    """Guida naturale per creare regole — non dump statistiche."""
    existing = get_rule_memories()
    lines = [
        "Certo. Possiamo fissare regole che terrò sempre presenti.",
    ]
    if existing:
        lines.append("\nRegole già attive:")
        for entry in existing[:5]:
            lines.append(f"• {entry.get('text', '').replace(chr(10), ' ')[:200]}")
    lines.append(
        "\nPer salvare una regola scrivi, ad esempio:\n"
        "«ricorda: rispondi sempre in modo breve, senza asterischi»\n\n"
        "Oppure elenca le regole che vuoi e le memorizzo una per una."
    )
    return "\n".join(lines)


def looks_like_false_memory_denial(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(p in lower for p in _FALSE_MEMORY_DENIAL_PHRASES):
        return True
    if "remember" in lower and any(w in lower for w in ("devi", "usa", "fornisci", "carica")):
        return True
    if "recall" in lower and any(w in lower for w in ("devi", "usa", "dimostra")):
        return True
    return False


MAC_MEMORY_TAGS = ("knowledge-mac", "mac-fleet", "mac")


def get_memories_by_tags(tags: list[str] | tuple[str, ...], limit: int = 10) -> list[dict]:
    """Ultime memorie che contengono almeno uno dei tag indicati."""
    tag_set = {str(t).lower() for t in tags}
    out: list[dict] = []
    for entry in reversed(_load()):
        entry_tags = {str(t).lower() for t in (entry.get("tags") or [])}
        if entry_tags & tag_set:
            out.append(entry)
            if len(out) >= limit:
                break
    return out


def count_memories_by_tags(tags: list[str] | tuple[str, ...]) -> int:
    tag_set = {str(t).lower() for t in tags}
    return sum(
        1 for e in _load()
        if {str(t).lower() for t in (e.get("tags") or [])} & tag_set
    )


def get_memory_context_for_brain(user_text: str | None = None) -> str | None:
    """Contesto memoria per il system prompt — stats + conoscenza Mac/recenti."""
    entries = _load()
    if not entries:
        return None

    lower = (user_text or "").lower()
    memory_question = any(k in lower for k in MEMORY_QUERY_KEYWORDS)
    mac_question = any(k in lower for k in ("mac", "fleet", "cursor", "ssh", "mini"))

    stats = get_knowledge_stats()
    mac_count = count_memories_by_tags(["knowledge-mac"])
    mac_entries = get_memories_by_tags(["knowledge-mac", "mac-fleet"], limit=8)

    lines = ["=== MEMORIA ATTIVA (long_term.json) ==="]
    lines.append(
        f"Totale: {stats['memories']} voci "
        f"(utente: {stats['user_memories']}, JANIS: {stats['janis_memories']})."
    )
    if mac_count:
        lines.append(f"Conoscenza Mac (scan SSH): {mac_count} voci tag knowledge-mac.")

    if memory_question or mac_question or mac_entries:
        fleet = get_memories_by_tags(["mac-fleet"], limit=1)
        if fleet:
            lines.append(f"\nPanoramica fleet: {fleet[0].get('text', '')[:320]}")
        if mac_entries:
            lines.append("\nProgetti Mac in memoria:")
            for entry in mac_entries[:6]:
                if entry.get("text", "").startswith("[Mac Fleet]"):
                    continue
                lines.append(f"• {entry.get('text', '')[:220]}")
        if memory_question:
            lines.append("\nMemorie recenti:")
            for entry in entries[-5:]:
                lines.append(
                    f"• [{entry.get('timestamp', '')[:10]}] {entry.get('text', '')[:200]}"
                )

    return "\n".join(lines)


def search_memories(query: str) -> list[dict]:
    """Ricerca testuale sincrona (API REST)."""
    q = (query or "").strip().lower()
    entries = _load()
    if not q:
        return entries[-10:]
    if q in MAC_MEMORY_TAGS or q == "mac":
        return get_memories_by_tags(["knowledge-mac", "mac-fleet", "mac"], limit=20)
    return [
        e for e in entries
        if q in e.get("text", "").lower()
        or any(q in t.lower() for t in e.get("tags", []))
    ][:20]


async def search_memories_async(query: str) -> list[dict]:
    q = (query or "").strip().lower()
    entries = _load()
    if not q:
        return entries[-10:]
    if q in MAC_MEMORY_TAGS or q == "mac":
        return get_memories_by_tags(["knowledge-mac", "mac-fleet", "mac"], limit=20)

    # Ricerca testuale
    text_matches = [
        e for e in entries
        if q in e.get("text", "").lower()
        or any(q in t.lower() for t in e.get("tags", []))
    ]

    # Ricerca semantica opzionale
    semantic = await _semantic_search(entries, query, limit=10)
    seen = set()
    merged = []
    for e in semantic + text_matches:
        eid = e.get("id")
        if eid and eid not in seen:
            seen.add(eid)
            merged.append(e)
    return merged[:20]


@register("remember")
async def remember(args: dict) -> str:
    text = (args.get("text") or "").strip()
    if not text:
        return "Errore: 'text' obbligatorio."
    tags = _normalize_tags(args.get("tags") or [])
    entries = _load()
    source = (args.get("source") or "user").strip().lower()
    if source not in ("user", "janis"):
        source = "user"

    dup = _find_duplicate(entries, text)
    if dup:
        dup["text"] = text
        dup["tags"] = _normalize_tags(list(set(dup.get("tags", []) + tags)))
        dup["timestamp"] = datetime.now().isoformat()
        _save(entries)
        return f"Memoria aggiornata (duplicato): {text[:100]}"

    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "tags": tags,
        "source": source,
        "timestamp": datetime.now().isoformat(),
    }
    entries.append(entry)
    _save(entries)
    try:
        from backend.core.qdrant_client import upsert_memory
        await upsert_memory(text, metadata={"tags": tags, "source": "remember"})
    except Exception:
        pass
    return f"Memorizzato: {text[:100]}"


@register("recall")
async def recall(args: dict) -> str:
    query = (args.get("query") or "").strip()
    entries = _load()
    if not query:
        recent = entries[-5:]
        if not recent:
            return "Nessuna memoria salvata."
        return "\n".join(f"- [{e['timestamp'][:10]}] {e['text']}" for e in recent)

    matches = await search_memories_async(query)
    if not matches:
        return f"Nessun ricordo per: {query}"
    return "\n".join(f"- [{e['timestamp'][:10]}] {e['text']}" for e in matches[-10:])


@register("semantic_recall")
async def semantic_recall(args: dict) -> str:
    """Ricerca semantica via Qdrant + embedding Ollama."""
    query = (args.get("query") or "").strip()
    if not query:
        return "Query obbligatoria per semantic_recall."
    from backend.core.qdrant_client import qdrant_available, search_memory

    if not await qdrant_available():
        return "Qdrant non raggiungibile — usa recall file-based o avvia infra/qdrant/start-qdrant.sh"
    hits = await search_memory(query, limit=int(args.get("limit") or 5))
    if not hits:
        return f"Nessun match semantico per: {query}"
    lines = []
    for h in hits:
        score = h.get("score")
        sc = f" ({score:.2f})" if score is not None else ""
        lines.append(f"-{sc} {h.get('text', '')[:300]}")
    return "\n".join(lines)


@register("memory_status")
async def memory_status(args: dict) -> str:
    """Riepilogo memoria persistente — stats, Mac fleet, voci recenti."""
    _ = args
    stats = get_knowledge_stats()
    entries = _load()
    mac_count = count_memories_by_tags(["knowledge-mac"])
    lines = [
        f"Memorie totali: {stats['memories']} "
        f"(utente: {stats['user_memories']}, janis: {stats['janis_memories']})",
        f"Conoscenza Mac (knowledge-mac): {mac_count} voci",
    ]
    fleet = get_memories_by_tags(["mac-fleet"], limit=1)
    if fleet:
        lines.append(f"Fleet: {fleet[0].get('text', '')[:300]}")
    mac_samples = [
        e for e in get_memories_by_tags(["knowledge-mac"], limit=6)
        if not (e.get("text") or "").startswith("[Mac Fleet]")
    ]
    if mac_samples:
        lines.append("Progetti Mac (campione):")
        for entry in mac_samples[:4]:
            lines.append(f"- {entry.get('text', '')[:180]}")
    recent = entries[-3:]
    if recent:
        lines.append("Ultime memorie:")
        for entry in recent:
            lines.append(f"- [{entry.get('timestamp', '')[:10]}] {entry.get('text', '')[:150]}")
    return "\n".join(lines)
