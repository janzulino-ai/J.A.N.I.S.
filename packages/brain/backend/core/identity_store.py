"""Identità locale — embedding leggeri da volto (solo LAN, mai cloud)."""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path

from backend.config import settings


def _identity_dir() -> Path:
    p = Path(settings.JANIS_PROJECT_DIR) / "data" / "identity"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _vector_from_b64(image_b64: str, grid: int = 8) -> list[float]:
    try:
        from PIL import Image
        import io
    except ImportError:
        raw = base64.b64decode(image_b64.split(",")[-1])
        # fallback: byte histogram
        hist = [0.0] * 256
        for b in raw[:8192]:
            hist[b % 256] += 1
        s = math.sqrt(sum(x * x for x in hist)) or 1.0
        return [x / s for x in hist[:grid * grid]]

    raw = base64.b64decode(image_b64.split(",")[-1])
    img = Image.open(io.BytesIO(raw)).convert("L").resize((grid, grid))
    pixels = list(img.getdata())
    vec = [float(p) / 255.0 for p in pixels]
    s = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / s for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    return dot


def enroll(display_name: str, frames_b64: list[str]) -> dict:
    if not frames_b64:
        raise ValueError("Nessun frame")
    vectors = [_vector_from_b64(f) for f in frames_b64]
    avg = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(vectors[0]))]
    s = math.sqrt(sum(x * x for x in avg)) or 1.0
    avg = [x / s for x in avg]
    record = {
        "display_name": display_name.strip(),
        "embedding": avg,
        "frame_count": len(frames_b64),
    }
    path = _identity_dir() / "enrolled.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"ok": True, "display_name": record["display_name"], "frame_count": len(frames_b64)}


def verify(image_b64: str, threshold: float = 0.92) -> dict:
    path = _identity_dir() / "enrolled.json"
    if not path.exists():
        return {"verified": False, "reason": "not_enrolled"}
    record = json.loads(path.read_text(encoding="utf-8"))
    vec = _vector_from_b64(image_b64)
    score = _cosine(vec, record.get("embedding", []))
    verified = score >= threshold
    return {
        "verified": verified,
        "score": round(score, 4),
        "display_name": record.get("display_name") if verified else None,
    }
