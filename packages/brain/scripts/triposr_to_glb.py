#!/usr/bin/env python3
"""
Genera mesh 3D 360° da janis-texture.png con TripoSR.

Su Windows torchmcubes spesso non compila (manca CUDA Toolkit).
Patch: marching cubes via scikit-image prima di importare TripoSR.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIPOSR_DIR = ROOT / "tools" / "TripoSR"
ASSETS = ROOT / "frontend" / "assets"
DEFAULT_INPUT = ASSETS / "janis-texture.png"
DEFAULT_OUTPUT = ASSETS / "janis.glb"


def _patch_torchmcubes() -> None:
    """Inject CPU marching_cubes so TripoSR runs without torchmcubes."""
    import numpy as np
    import torch
    from skimage.measure import marching_cubes

    def marching_cubes_compat(volume, threshold):
        device = volume.device if isinstance(volume, torch.Tensor) else torch.device("cpu")
        if isinstance(volume, torch.Tensor):
            vol = volume.detach().cpu().numpy()
        else:
            vol = np.asarray(volume)
        verts, faces, _, _ = marching_cubes(vol, level=float(threshold))
        return (
            torch.from_numpy(verts.astype(np.float32)).to(device),
            torch.from_numpy(faces.astype(np.int64)).to(device),
        )

    mod = types.ModuleType("torchmcubes")
    mod.marching_cubes = marching_cubes_compat
    sys.modules["torchmcubes"] = mod


def _ensure_triposr_path() -> None:
    if not TRIPOSR_DIR.is_dir():
        raise FileNotFoundError(f"TripoSR non trovato: {TRIPOSR_DIR}")
    if str(TRIPOSR_DIR) not in sys.path:
        sys.path.insert(0, str(TRIPOSR_DIR))


def generate(
    input_path: Path,
    output_path: Path,
    *,
    device: str = "cuda:0",
    mc_resolution: int = 256,
    bake_texture_atlas: bool = False,
    texture_resolution: int = 2048,
    no_remove_bg: bool = True,
) -> Path:
    import numpy as np
    import torch
    import xatlas
    from PIL import Image

    _patch_torchmcubes()
    _ensure_triposr_path()

    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    if not input_path.is_file():
        raise FileNotFoundError(f"Immagine non trovata: {input_path}")

    if not torch.cuda.is_available() and device.startswith("cuda"):
        device = "cpu"
        print("[TripoSR] CUDA non disponibile — uso CPU (più lento)")

    print(f"[TripoSR] Caricamento modello stabilityai/TripoSR su {device}...")
    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(device)

    if no_remove_bg:
        image = np.array(Image.open(input_path).convert("RGB"))
        pil_image = Image.fromarray(image)
    else:
        import rembg

        session = rembg.new_session()
        pil_image = remove_background(Image.open(input_path), session)
        pil_image = resize_foreground(pil_image, 0.85)
        arr = np.array(pil_image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        pil_image = Image.fromarray((arr * 255.0).astype(np.uint8))

    print(f"[TripoSR] Inferenza da {input_path.name}...")
    with torch.no_grad():
        scene_codes = model([pil_image], device=device)

    print(f"[TripoSR] Estrazione mesh (resolution={mc_resolution})...")
    meshes = model.extract_mesh(scene_codes, True, resolution=mc_resolution)
    mesh = meshes[0]

    work_dir = ROOT / "tools" / "triposr-output"
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp_glb = work_dir / "janis-mesh.glb"

    if bake_texture_atlas:
        import xatlas
        from tsr.bake_texture import bake_texture as triposr_bake_texture

        tmp_obj = work_dir / "janis-mesh.obj"
        print("[TripoSR] Baking texture atlas...")
        bake_output = triposr_bake_texture(mesh, model, scene_codes[0], texture_resolution)
        xatlas.export(
            str(tmp_obj),
            mesh.vertices[bake_output["vmapping"]],
            bake_output["indices"],
            bake_output["uvs"],
            mesh.vertex_normals[bake_output["vmapping"]],
        )
        tex_path = work_dir / "janis-texture-baked.png"
        Image.fromarray((bake_output["colors"] * 255.0).astype(np.uint8)).transpose(
            Image.FLIP_TOP_BOTTOM
        ).save(tex_path)
        import trimesh

        loaded = trimesh.load(str(tmp_obj), process=False)
        loaded.visual.material.image = Image.open(tex_path)
        loaded.export(str(tmp_glb))
    else:
        print("[TripoSR] Esportazione GLB con vertex colors...")
        mesh.export(str(tmp_glb))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmp_glb, output_path)
    print(f"[TripoSR] Esportato: {output_path} ({output_path.stat().st_size // 1024} KB)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="TripoSR → janis.glb")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--mc-resolution", type=int, default=256)
    parser.add_argument("--bake-texture", action="store_true", help="Atlas UV (può fallire su Windows)")
    parser.add_argument("--remove-bg", action="store_true", help="Rimuovi sfondo con rembg")
    args = parser.parse_args()

    generate(
        args.input,
        args.output,
        device=args.device,
        mc_resolution=args.mc_resolution,
        bake_texture_atlas=args.bake_texture,
        no_remove_bg=not args.remove_bg,
    )


if __name__ == "__main__":
    main()
