"""API identità — enroll/verify volto locale."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.device_auth import require_device_token
from backend.core import identity_store

router = APIRouter(dependencies=[Depends(require_device_token)])


class EnrollBody(BaseModel):
    display_name: str = Field(min_length=1)
    frames: list[str] = Field(min_length=1, description="JPEG base64")


class VerifyBody(BaseModel):
    image_base64: str


@router.post("/api/identity/enroll")
async def identity_enroll(body: EnrollBody):
    return identity_store.enroll(body.display_name, body.frames)


@router.post("/api/identity/verify")
async def identity_verify(body: VerifyBody):
    return identity_store.verify(body.image_base64)
