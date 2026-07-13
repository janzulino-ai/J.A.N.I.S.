#!/usr/bin/env python3
"""
Genera modello GLB 3D ruotabile da immagine avatar JANIS.
Usa depth map euristica (volto in rilievo) — eseguibile in locale.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom
import trimesh

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "frontend" / "assets"
INPUT = ASSETS / "janis-texture.png"
FALLBACK = ASSETS / "janis-v3d.png"
OUTPUT = ASSETS / "janis.glb"

SEG_W = 128
DEPTH_SCALE = 0.42


def pick_input() -> Path:
    if INPUT.exists():
        return INPUT
    if FALLBACK.exists():
        return FALLBACK
    raise FileNotFoundError("Nessuna texture avatar trovata in frontend/assets/")


def build_depth(rgba: np.ndarray) -> np.ndarray:
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    lum = rgba[:, :, :3].astype(np.float32).mean(axis=2) / 255.0

    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.5, h * 0.20
    dist = np.sqrt(((xx - cx) / (w * 0.32)) ** 2 + ((yy - cy) / (h * 0.22)) ** 2)
    face = np.clip(1.0 - dist, 0, 1) ** 1.4

    body_cy = h * 0.55
    body = np.exp(-((yy - body_cy) ** 2) / (2 * (h * 0.28) ** 2)) * 0.35

    depth = face * 0.55 + body * 0.25 + (1.0 - lum) * 0.2
    depth *= alpha
    depth = gaussian_filter(depth, sigma=2.8)
    dmin, dmax = depth.min(), depth.max()
    if dmax > dmin:
        depth = (depth - dmin) / (dmax - dmin)
    return depth


def make_mesh(rgba: np.ndarray, depth: np.ndarray) -> trimesh.Trimesh:
    h, w = rgba.shape[:2]
    sh = max(64, int(SEG_W * h / w))
    sw = SEG_W

    img = Image.fromarray(rgba).resize((sw, sh), Image.Resampling.LANCZOS)
    arr = np.array(img)
    depth_s = zoom(depth, (sh / h, sw / w), order=1)

    aspect = sw / sh
    plane_h = 2.6
    plane_w = plane_h * aspect

    verts = []
    uvs = []
    for j in range(sh):
        for i in range(sw):
            u = i / (sw - 1)
            v = 1.0 - j / (sh - 1)
            x = (u - 0.5) * plane_w
            y = (v - 0.5) * plane_h
            z = depth_s[j, i] * DEPTH_SCALE
            if arr[j, i, 3] < 10:
                z = 0.0
            verts.append([x, y, z])
            uvs.append([u, v])

    faces = []
    for j in range(sh - 1):
        for i in range(sw - 1):
            a = j * sw + i
            b = a + 1
            c = a + sw
            d = c + 1
            if arr[j, i, 3] < 10 and arr[j, i + 1, 3] < 10:
                continue
            faces.append([a, b, d])
            faces.append([a, d, c])

    verts = np.array(verts, dtype=np.float64)
    faces = np.array(faces, dtype=np.int64)
    uvs = np.array(uvs, dtype=np.float64)

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=uvs,
        image=Image.fromarray(rgba),
    )
    return mesh


def main():
    src = pick_input()
    print(f"Input: {src}")
    rgba = np.array(Image.open(src).convert("RGBA"))
    depth = build_depth(rgba)
    mesh = make_mesh(rgba, depth)
    mesh.apply_translation(-mesh.centroid)
    ASSETS.mkdir(parents=True, exist_ok=True)
    mesh.export(OUTPUT)
    print(f"Esportato: {OUTPUT} ({len(mesh.vertices)} vertici, {len(mesh.faces)} facce)")


if __name__ == "__main__":
    main()
