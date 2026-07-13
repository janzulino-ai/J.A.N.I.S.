import base64
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings

router = APIRouter()
logger = logging.getLogger("JANIS.STT")

_whisper_model = None
_engine_info: dict | None = None

SUPPORTED_FORMATS = ("webm", "ogg", "wav", "mp3", "m4a", "opus", "flac")
INSTALL_HINT = "pip install faster-whisper>=1.0.0  (modello scaricato al primo uso)"


def _probe_engines() -> dict:
    global _engine_info
    if _engine_info is not None:
        return _engine_info

    info: dict = {
        "stt_enabled": settings.STT_ENABLED,
        "model": settings.STT_MODEL,
        "faster_whisper": False,
        "openai_whisper": False,
        "engine": None,
        "install_hint": None,
        "ready": False,
    }

    if not settings.STT_ENABLED:
        info["install_hint"] = "STT disabilitato (STT_ENABLED=false in .env)"
        _engine_info = info
        return info

    try:
        import faster_whisper  # noqa: F401

        info["faster_whisper"] = True
        info["engine"] = "faster-whisper"
        info["ready"] = True
    except ImportError:
        whisper_cli = shutil.which("whisper")
        if whisper_cli:
            info["openai_whisper"] = True
            info["engine"] = "openai-whisper-cli"
            info["ready"] = True
        else:
            try:
                import whisper  # noqa: F401

                info["openai_whisper"] = True
                info["engine"] = "openai-whisper"
                info["ready"] = True
            except ImportError:
                info["install_hint"] = INSTALL_HINT

    _engine_info = info
    return info


def _get_faster_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel

    logger.info("Caricamento modello STT faster-whisper: %s", settings.STT_MODEL)
    _whisper_model = WhisperModel(
        settings.STT_MODEL,
        device="cpu",
        compute_type="int8",
    )
    return _whisper_model


def _transcribe_with_faster_whisper(path: str, language: str) -> dict:
    model = _get_faster_whisper_model()
    segments, info = model.transcribe(
        path,
        language=language or None,
        beam_size=5,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {
        "text": text,
        "language": info.language or language or "it",
        "engine": "faster-whisper",
    }


def _transcribe_with_openai_whisper_module(path: str, language: str) -> dict:
    import whisper

    if not hasattr(_transcribe_with_openai_whisper_module, "_model"):
        logger.info("Caricamento modello STT openai-whisper: %s", settings.STT_MODEL)
        _transcribe_with_openai_whisper_module._model = whisper.load_model(settings.STT_MODEL)
    model = _transcribe_with_openai_whisper_module._model
    result = model.transcribe(path, language=language or "it")
    return {
        "text": (result.get("text") or "").strip(),
        "language": result.get("language") or language or "it",
        "engine": "openai-whisper",
    }


def _transcribe_with_whisper_cli(path: str, language: str) -> dict:
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        raise HTTPException(status_code=503, detail="whisper CLI non trovato")

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        cmd = [
            whisper_bin,
            path,
            "--model",
            settings.STT_MODEL,
            "--language",
            language or "it",
            "--output_format",
            "txt",
            "--output_dir",
            str(out_dir),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            logger.error("whisper CLI failed: %s", proc.stderr)
            raise HTTPException(status_code=500, detail=f"Trascrizione fallita: {proc.stderr[:200]}")

        txt_files = list(out_dir.glob("*.txt"))
        text = txt_files[0].read_text(encoding="utf-8").strip() if txt_files else ""
        return {"text": text, "language": language or "it", "engine": "openai-whisper-cli"}


def _transcribe_file(path: str, language: str = "it") -> dict:
    probe = _probe_engines()
    if not settings.STT_ENABLED:
        raise HTTPException(status_code=503, detail="STT disabilitato in configurazione")
    if not probe.get("ready"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "STT non disponibile",
                "install": probe.get("install_hint") or INSTALL_HINT,
            },
        )

    engine = probe["engine"]
    try:
        if engine == "faster-whisper":
            return _transcribe_with_faster_whisper(path, language)
        if engine == "openai-whisper":
            return _transcribe_with_openai_whisper_module(path, language)
        if engine == "openai-whisper-cli":
            return _transcribe_with_whisper_cli(path, language)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("STT transcribe failed")
        raise HTTPException(status_code=500, detail=f"Trascrizione fallita: {e}") from e

    raise HTTPException(status_code=503, detail="Nessun motore STT disponibile")


def _save_upload_to_temp(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with open(fd, "wb") as f:
            f.write(data)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return path


class STTJsonBody(BaseModel):
    audio_base64: str = Field(min_length=8)
    format: str = Field(default="webm")
    language: str = Field(default="it")


def _stt_diagnostic_payload() -> dict:
    probe = _probe_engines()
    return {
        **probe,
        "language_default": "it",
        "supported_formats": list(SUPPORTED_FORMATS),
        "endpoint": "/api/stt",
        "note": (
            "STT locale via Whisper — non richiede Google Speech API. "
            "Primo avvio può scaricare il modello (~150 MB per base)."
        ),
    }


@router.get("/api/stt/diagnostic")
@router.post("/api/stt/diagnostic")
async def stt_diagnostic():
    return _stt_diagnostic_payload()


@router.post("/api/stt")
async def transcribe(
    request: Request,
    file: UploadFile | None = File(None),
    audio_base64: str | None = Form(None),
    format: str = Form("webm"),
    language: str = Form("it"),
):
    """Trascrive audio (multipart file, form base64 o JSON base64)."""
    lang = (language or "it").strip() or "it"
    raw: bytes | None = None
    ext = (format or "webm").lstrip(".").lower()

    if file is not None:
        raw = await file.read()
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
    elif audio_base64:
        try:
            b64 = audio_base64.split(",", 1)[-1]
            raw = base64.b64decode(b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Base64 non valido: {e}") from e
    else:
        ct = request.headers.get("content-type", "")
        if "application/json" in ct:
            try:
                body = STTJsonBody.model_validate(await request.json())
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"JSON non valido: {e}") from e
            try:
                b64 = body.audio_base64.split(",", 1)[-1]
                raw = base64.b64decode(b64)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Base64 non valido: {e}") from e
            ext = (body.format or "webm").lstrip(".").lower()
            lang = body.language or "it"
        else:
            raise HTTPException(
                status_code=400,
                detail="Invia multipart 'file', form 'audio_base64' o JSON {audio_base64, format}",
            )

    if not raw:
        raise HTTPException(status_code=400, detail="Audio vuoto")

    if ext not in SUPPORTED_FORMATS:
        ext = "webm"

    tmp_path = _save_upload_to_temp(raw, f".{ext}")
    try:
        return _transcribe_file(tmp_path, lang)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
