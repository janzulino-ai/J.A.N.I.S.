import io
import logging

import edge_tts
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.config import settings

router = APIRouter()
logger = logging.getLogger("JANIS.TTS")

# Voci femminili italiane consigliate (Microsoft Neural)
ITALIAN_FEMALE_VOICES = {
    "isabella": "it-IT-IsabellaNeural",   # calda, espressiva — default "cantante"
    "elsa": "it-IT-ElsaNeural",           # morbida, elegante
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = None
    rate: str | None = None
    pitch: str | None = None


async def _synthesize(text: str, voice: str, rate: str, pitch: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()


@router.get("/api/tts/voices")
async def list_voices():
    return {
        "default": settings.JANIS_TTS_VOICE,
        "rate": settings.JANIS_TTS_RATE,
        "pitch": settings.JANIS_TTS_PITCH,
        "italian_female": [
            {"id": v, "label": k.capitalize()} for k, v in ITALIAN_FEMALE_VOICES.items()
        ],
        "note": (
            "Voci neurali Microsoft — profilo femminile italiano giovane e melodico. "
            "Isabella: più espressiva e pop. Elsa: più morbida e calda."
        ),
    }


@router.post("/api/tts")
async def synthesize(request: TTSRequest):
    voice = request.voice or settings.JANIS_TTS_VOICE
    rate = request.rate or settings.JANIS_TTS_RATE
    pitch = request.pitch or settings.JANIS_TTS_PITCH
    text = request.text.strip()

    try:
        audio = await _synthesize(text, voice, rate, pitch)
    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(status_code=500, detail=f"Sintesi vocale fallita: {e}") from e

    if not audio:
        raise HTTPException(status_code=500, detail="Audio vuoto")

    return Response(content=audio, media_type="audio/mpeg")


@router.get("/api/tts")
async def synthesize_get(
    text: str = Query(..., min_length=1, max_length=4000),
    voice: str | None = None,
):
    req = TTSRequest(text=text, voice=voice)
    return await synthesize(req)
