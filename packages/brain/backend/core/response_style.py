"""Stile risposte JANIS — testo da mostrare vs testo da leggere ad alta voce."""
from __future__ import annotations

import re


def compute_tts_text(full_text: str, *, max_chars: int = 420) -> str:
    """Estrae solo la parte conversazionale da sintetizzare (no codice, no elenchi lunghi)."""
    text = (full_text or "").strip()
    if not text:
        return ""

    # Taglia prima di blocchi tecnici evidenti
    for marker in (
        "\n```",
        "\n### ",
        "\n## ",
        "\n---",
        "\n| ",
        "\n=== ",
        "\nSTRUMENTI",
        "\nBackend\n",
        "\nProssim",
    ):
        idx = text.find(marker)
        if idx > 40:
            text = text[:idx]

    # Rimuovi codice e markdown (anche fence non chiuso)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"```[\s\S]*", " ", text)
    text = re.sub(r"`[^`\n]+`", " ", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[🟢🟡🔴⏸️✓✗▶◆🔧🌐⌨💬🍎＋🔊🔇]+", " ", text)

    sentences: list[str] = []
    total = 0
    for raw in re.split(r"(?<=[.!?…])\s+", text):
        s = raw.strip()
        if len(s) < 10:
            continue
        if re.match(r"^[\d\-•*]+\s", s):
            continue
        if re.search(r"\{[^}]*\"tool\"", s):
            continue
        if s.count("/") >= 3 and "." in s:  # path file
            continue
        sentences.append(s)
        total += len(s)
        if len(sentences) >= 3 or total >= max_chars:
            break

    out = " ".join(sentences).strip()
    if not out:
        # fallback: prime parole pulite
        clean = re.sub(r"\s+", " ", text)
        out = clean[: min(220, len(clean))]
    return out[:max_chars].strip()


def conversational_improve_summary(
    reflect_summary: str,
    prefs_count: int,
    open_code_title: str | None,
) -> str:
    """Risposta breve e naturale dopo un ciclo reflect."""
    lines = []
    if reflect_summary:
        short = reflect_summary.strip()
        if len(short) > 280:
            short = short[:277].rsplit(" ", 1)[0] + "…"
        lines.append(short)
    elif prefs_count:
        lines.append(f"Ho aggiornato {prefs_count} preferenze tue che terrò presente da ora in poi.")
    else:
        lines.append("Ho fatto un giro di auto-analisi su come sto rispondendo e su cosa posso migliorare.")

    if open_code_title:
        lines.append(
            f"La modifica al codice più urgente che vedo è «{open_code_title}». "
            "Se vuoi la applico con autodev, altrimenti dimmi cosa ti dà fastidio adesso."
        )
    else:
        lines.append("Dimmi cosa non ti convince nel modo in cui rispondo e lo sistemiamo.")
    return "\n\n".join(lines)
