"""Generazione media locale — ComfyUI (W6g)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import httpx

from backend.config import settings
from backend.core.tools.registry import register

logger = logging.getLogger("JANIS.Media")


def _comfy_base() -> str:
    return (getattr(settings, "COMFYUI_URL", None) or "http://127.0.0.1:8188").rstrip("/")


def _comfy_output_dir() -> Path:
    """Cartella output Comfy — Windows host o path WSL /mnt/c/..."""
    custom = (getattr(settings, "COMFYUI_OUTPUT_DIR", None) or "").strip()
    candidates: list[Path] = []
    if custom:
        candidates.append(Path(custom))
    home = Path.home()
    candidates.append(home / "ComfyUI" / "output")
    # Da WSL: Comfy gira su Windows
    win_user = os.environ.get("WINDOWS_USERNAME") or os.environ.get("USER") or ""
    for user in filter(None, {win_user, "agenz"}):
        candidates.append(Path(f"/mnt/c/Users/{user}/ComfyUI/output"))
        candidates.append(Path(f"C:/Users/{user}/ComfyUI/output"))
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    p = home / "ComfyUI" / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _comfy_online() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_comfy_base()}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def _list_checkpoints() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{_comfy_base()}/object_info/CheckpointLoaderSimple")
            if r.status_code != 200:
                return []
            data = r.json() or {}
            opts = (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name")
            )
            if isinstance(opts, list) and opts and isinstance(opts[0], list):
                return [str(x) for x in opts[0] if x and "put_" not in str(x)]
            return []
    except Exception:
        logger.debug("list checkpoints fail", exc_info=True)
        return []


async def _pick_checkpoint(preferred: str | None = None) -> str | None:
    available = await _list_checkpoints()
    if not available:
        return None
    pref = (preferred or getattr(settings, "COMFYUI_CHECKPOINT", None) or "").strip()
    if pref and pref in available:
        return pref
    # prefer sd1.5 / small names
    for name in available:
        low = name.lower()
        if "v1-5" in low or "sd15" in low or "dreamshaper" in low:
            return name
    return available[0]


def _txt2img_workflow(
    prompt: str,
    negative: str,
    width: int,
    height: int,
    ckpt: str,
) -> dict:
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(uuid.uuid4().int % 2**31),
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality", "clip": ["4", 1]},
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "janis", "images": ["8", 0]},
        },
    }


async def _wait_history(client: httpx.AsyncClient, prompt_id: str, timeout: float = 300.0) -> dict | None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"{_comfy_base()}/history/{prompt_id}")
        if r.status_code == 200:
            data = r.json() or {}
            if prompt_id in data:
                return data[prompt_id]
        await asyncio.sleep(1.5)
    return None


@register("image_gen")
async def image_gen(args: dict) -> str:
    """Genera immagine via ComfyUI locale. args: prompt, negative, width, height, wait=true"""
    prompt = (args.get("prompt") or args.get("text") or "").strip()
    if not prompt:
        return "prompt obbligatorio"
    if not await _comfy_online():
        return (
            f"ComfyUI non raggiungibile su {_comfy_base()}.\n"
            "Avvia ComfyUI (RTX locale) o imposta COMFYUI_URL in .env."
        )

    ckpt = await _pick_checkpoint(args.get("checkpoint"))
    if not ckpt:
        return (
            "Nessun checkpoint in ComfyUI/models/checkpoints.\n"
            "Scarica es. v1-5-pruned-emaonly.safetensors da HuggingFace "
            "(Comfy-Org/stable-diffusion-v1-5-archive) e riprova."
        )

    from backend.core.orchestrator.cost_router import cost_router

    if not cost_router.can_use_agent("brain-local", 0.0):
        return "Budget agente esaurito — image_gen bloccato"

    width = int(args.get("width") or 512)
    height = int(args.get("height") or 512)
    # clamp for VRAM safety
    width = max(256, min(width, 1024))
    height = max(256, min(height, 1024))
    negative = (args.get("negative") or "").strip()
    wait = str(args.get("wait", "true")).lower() not in ("0", "false", "no")
    workflow = _txt2img_workflow(prompt, negative, width, height, ckpt)
    client_id = f"janis-{uuid.uuid4().hex[:8]}"
    try:
        async with httpx.AsyncClient(timeout=360.0) as client:
            r = await client.post(
                f"{_comfy_base()}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            if r.status_code >= 400:
                return f"ComfyUI error {r.status_code}: {r.text[:1200]}"
            data = r.json()
            if data.get("node_errors"):
                return f"ComfyUI node_errors: {json.dumps(data['node_errors'], ensure_ascii=False)[:1200]}"
            prompt_id = data.get("prompt_id") or data.get("promptId")
            out_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "images"
            out_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "checkpoint": ckpt,
                "comfy": _comfy_base(),
                "width": width,
                "height": height,
            }
            if not wait:
                meta_path = out_dir / f"{prompt_id or client_id}.json"
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                return (
                    f"Immagine in coda ComfyUI (checkpoint={ckpt}).\n"
                    f"prompt_id={prompt_id}\nmeta={meta_path}"
                )

            hist = await _wait_history(client, prompt_id, timeout=300.0)
            if not hist:
                return f"Timeout attesa ComfyUI prompt_id={prompt_id} (checkpoint={ckpt})"

            images = []
            for node_out in (hist.get("outputs") or {}).values():
                for img in node_out.get("images") or []:
                    images.append(img)

            paths = []
            comfy_out = _comfy_output_dir()
            for img in images:
                fname = img.get("filename") or ""
                sub = img.get("subfolder") or ""
                src = comfy_out / sub / fname if sub else comfy_out / fname
                if src.is_file():
                    dest = out_dir / fname
                    dest.write_bytes(src.read_bytes())
                    paths.append(str(dest))
                else:
                    # prova view API
                    try:
                        vr = await client.get(
                            f"{_comfy_base()}/view",
                            params={
                                "filename": fname,
                                "subfolder": sub,
                                "type": img.get("type") or "output",
                            },
                        )
                        if vr.status_code == 200 and vr.content:
                            dest = out_dir / (fname or f"{prompt_id}.png")
                            dest.write_bytes(vr.content)
                            paths.append(str(dest))
                    except Exception:
                        pass

            public = (getattr(settings, "PUBLIC_BASE_URL", None) or f"http://127.0.0.1:{settings.PORT}").rstrip("/")
            urls = []
            for p in paths:
                name = Path(p).name
                urls.append(f"{public}/api/media/images/{name}")
            meta["images"] = paths or images
            meta["urls"] = urls
            meta_path = out_dir / f"{prompt_id or client_id}.json"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            if paths and urls:
                lines = [
                    f"Immagine generata (checkpoint={ckpt}).",
                    f"URL: {urls[0]}",
                    f"![immagine]({urls[0]})",
                ]
                for u in urls[1:]:
                    lines.append(f"URL: {u}")
                    lines.append(f"![immagine]({u})")
                lines.append(f"file: {paths[0]}")
                return "\n".join(lines)
            return (
                f"Generazione completata ma file non trovato in output.\n"
                f"prompt_id={prompt_id} checkpoint={ckpt}\n"
                f"Controlla {comfy_out}"
            )
    except Exception as e:
        logger.exception("image_gen")
        return f"Errore ComfyUI: {e}"


@register("video_gen")
async def video_gen(args: dict) -> str:
    """Genera video — richiede workflow Comfy video. args: prompt, frames"""
    prompt = (args.get("prompt") or args.get("text") or "").strip()
    if not prompt:
        return "prompt obbligatorio"
    if not await _comfy_online():
        return (
            f"ComfyUI non raggiungibile su {_comfy_base()}.\n"
            "Per video serve workflow AnimateDiff/SVD installato in ComfyUI."
        )
    frames = int(args.get("frames") or 16)
    out_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "video"
    out_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    meta = {
        "job_id": job_id,
        "prompt": prompt,
        "frames": frames,
        "status": "needs_video_workflow",
        "note": "Serve workflow AnimateDiff/SVD in ComfyUI.",
    }
    path = out_dir / f"{job_id}.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps(meta, ensure_ascii=False, indent=2)


@register("media_status")
async def media_status(_args: dict) -> str:
    online = await _comfy_online()
    ckpts = await _list_checkpoints() if online else []
    picked = await _pick_checkpoint() if online else None
    return json.dumps(
        {
            "comfyui_url": _comfy_base(),
            "online": online,
            "checkpoint_configured": getattr(settings, "COMFYUI_CHECKPOINT", "") or "",
            "checkpoint_active": picked,
            "checkpoints": ckpts[:20],
            "output_dir": str(_comfy_output_dir()),
            "tools": ["image_gen", "video_gen"],
        },
        ensure_ascii=False,
        indent=2,
    )
