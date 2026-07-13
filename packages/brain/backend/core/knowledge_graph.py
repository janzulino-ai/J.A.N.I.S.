"""Grafo conoscenza second-brain (stile Obsidian) da memorie JANIS."""
from __future__ import annotations

import hashlib
import math
import re
from backend.core.tools.memory_tool import _load


def _short_label(text: str, n: int = 28) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return (t[: n - 1] + "…") if len(t) > n else t


def _pos_from_id(node_id: str) -> tuple[float, float, float]:
    h = hashlib.sha256(node_id.encode()).digest()
    u = int.from_bytes(h[0:4], "big") / 0xFFFFFFFF
    v = int.from_bytes(h[4:8], "big") / 0xFFFFFFFF
    theta = u * math.pi * 2
    phi = math.acos(2 * v - 1)
    r = 0.55 + (int.from_bytes(h[8:10], "big") / 0xFFFF) * 0.35
    return (
        r * math.sin(phi) * math.cos(theta),
        r * math.sin(phi) * math.sin(theta),
        r * math.cos(phi),
    )


def build_knowledge_graph(limit: int = 64) -> dict:
    entries = _load()[-limit:]
    nodes: list[dict] = []
    edges: list[dict] = []
    by_tag: dict[str, list[str]] = {}
    last_by_source: dict[str, str] = {}

    for e in entries:
        nid = e.get("id") or str(hash(e.get("text", "")))
        source = e.get("source", "user")
        tags = e.get("tags") or []
        x, y, z = _pos_from_id(nid)
        nodes.append({
            "id": nid,
            "label": _short_label(e.get("text", "")),
            "source": source,
            "tags": tags,
            "x": round(x, 4),
            "y": round(y, 4),
            "z": round(z, 4),
            "size": 1.0 + min(2.0, len(e.get("text", "")) / 120),
        })
        prev = last_by_source.get(source)
        if prev:
            edges.append({"from": prev, "to": nid, "kind": "sequence"})
        last_by_source[source] = nid

        for tag in tags:
            t = str(tag).lower().strip()
            if not t:
                continue
            if t in by_tag:
                for other in by_tag[t][-3:]:
                    if other != nid:
                        edges.append({"from": other, "to": nid, "kind": "tag", "tag": t})
            by_tag.setdefault(t, []).append(nid)

    # dedupe edges
    seen = set()
    unique_edges = []
    for ed in edges:
        key = tuple(sorted((ed["from"], ed["to"])))
        if key in seen:
            continue
        seen.add(key)
        unique_edges.append(ed)

    return {"nodes": nodes, "edges": unique_edges, "count": len(nodes)}


def node_from_memory(entry: dict) -> dict:
    nid = entry.get("id") or str(hash(entry.get("text", "")))
    x, y, z = _pos_from_id(nid)
    return {
        "id": nid,
        "label": _short_label(entry.get("text", "")),
        "source": entry.get("source", "user"),
        "tags": entry.get("tags") or [],
        "x": round(x, 4),
        "y": round(y, 4),
        "z": round(z, 4),
        "size": 1.0,
    }
