"""Generazione media locale — ComfyUI (W6g)."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import httpx

from backend.config import settings
from backend.core.tools.registry import register

logger = logging.getLogger("JANIS.Media")


def _comfy_base() -> str:
    return (getattr(settings, "COMFYUI_URL", None) or "http://127.0.0.1:8188").rstrip("/")


async def _comfy_online() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_comfy_base()}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


def _txt2img_workflow(prompt: str, negative: str = "", width: int = 768, height: int = 768) -> dict:
    """Workflow minimale ComfyUI (CheckpointLoader → KSampler → SaveImage)."""
    ckpt = getattr(settings, "COMFYUI_CHECKPOINT", None) or "v1-5-pruned-emaonly.safetensors"
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


@register("image_gen")
async def image_gen(args: dict) -> str:
    """Genera immagine via ComfyUI locale. args: prompt, negative, width, height"""
    prompt = (args.get("prompt") or args.get("text") or "").strip()
    if not prompt:
        return "prompt obbligatorio"
    if not await _comfy_online():
        return (
            f"ComfyUI non raggiungibile su {_comfy_base()}.\n"
            "Avvia ComfyUI (RTX locale) o imposta COMFYUI_URL in .env."
        )

    from backend.core.orchestrator.cost_router import cost_router

    if not cost_router.can_use_agent("brain-local", 0.0):
        return "Budget agente esaurito — image_gen bloccato"

    width = int(args.get("width") or 768)
    height = int(args.get("height") or 768)
    negative = (args.get("negative") or "").strip()
    workflow = _txt2img_workflow(prompt, negative, width, height)
    client_id = f"janis-{uuid.uuid4().hex[:8]}"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{_comfy_base()}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            if r.status_code >= 400:
                return f"ComfyUI error {r.status_code}: {r.text[:800]}"
            data = r.json()
            prompt_id = data.get("prompt_id") or data.get("promptId")
            out_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "images"
            out_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "comfy": _comfy_base(),
                "width": width,
                "height": height,
            }
            meta_path = out_dir / f"{prompt_id or client_id}.json"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return (
                f"Immagine in coda ComfyUI.\n"
                f"prompt_id={prompt_id}\n"
                f"meta={meta_path}\n"
                f"Controlla output in ComfyUI output/ (prefix janis)."
            )
    except Exception as e:
        logger.exception("image_gen")
        return f"Errore ComfyUI: {e}"


@register("video_gen")
async def video_gen(args: dict) -> str:
    """Genera video — richiede workflow Comfy video o sidecar. args: prompt, frames"""
    prompt = (args.get("prompt") or args.get("text") or "").strip()
    if not prompt:
        return "prompt obbligatorio"
    if not await _comfy_online():
        return (
            f"ComfyUI non raggiungibile su {_comfy_base()}.\n"
            "Per video serve workflow AnimateDiff/SVD installato in ComfyUI.\n"
            "Cloud Veo/Sora: usa multimodal-mcp con budget (non default LOCAL_FIRST)."
        )
    frames = int(args.get("frames") or 16)
    # Queue stub metadata — full video workflow depends on user nodes
    out_dir = Path(settings.JANIS_PROJECT_DIR) / "data" / "media" / "video"
    out_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    meta = {
        "job_id": job_id,
        "prompt": prompt,
        "frames": frames,
        "status": "needs_video_workflow",
        "note": (
            "Comfy online ma video_gen richiede un workflow dedicato "
            "(AnimateDiff/SVD). Carica workflow in data/media/video/workflow.json "
            "o estendi media_tool."
        ),
    }
    path = out_dir / f"{job_id}.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps(meta, ensure_ascii=False, indent=2)


@register("media_status")
async def media_status(_args: dict) -> str:
    online = await _comfy_online()
    return json.dumps(
        {
            "comfyui_url": _comfy_base(),
            "online": online,
            "checkpoint": getattr(settings, "COMFYUI_CHECKPOINT", "") or "default",
            "tools": ["image_gen", "video_gen"],
        },
        ensure_ascii=False,
        indent=2,
    )
