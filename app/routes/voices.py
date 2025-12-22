from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_console_user
from app.models import Voice
from app.routes.shared import get_default_project
from app.schemas import VoiceOut, VoiceUpdateIn
from app.services.storage import to_public_file_url

console_router = APIRouter(prefix="/console", tags=["console-voices"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-voices"])


def _voice_out(v: Voice) -> VoiceOut:
    return VoiceOut(
        id=v.id,
        name=v.name,
        description=v.description,
        is_public=v.is_public,
        preview_audio_url=to_public_file_url(v.preview_audio_path) if v.preview_audio_path else "",
    )


@console_router.get("/voices/mine", response_model=list[VoiceOut])
async def my_voices(db: AsyncSession = Depends(get_db), user=Depends(require_console_user)):
    proj = await get_default_project(db, user)
    voices = (await db.execute(select(Voice).where(Voice.owner_project_id == proj.id).order_by(Voice.id.desc()))).scalars().all()
    return [_voice_out(v) for v in voices]


@console_router.patch("/voices/{voice_id}", response_model=VoiceOut)
async def update_voice(voice_id: int, payload: VoiceUpdateIn, db: AsyncSession = Depends(get_db), user=Depends(require_console_user)):
    proj = await get_default_project(db, user)
    v = (await db.execute(select(Voice).where(Voice.id == voice_id))).scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="voice_not_found")
    if v.owner_project_id != proj.id:
        raise HTTPException(status_code=403, detail="not_owner")
    if payload.description is not None:
        v.description = payload.description
    if payload.is_public is not None:
        v.is_public = payload.is_public
    db.add(v)
    await db.flush()
    return _voice_out(v)


@console_router.get("/voices/public", response_model=list[VoiceOut])
@openapi_router.get("/voices/public", response_model=list[VoiceOut])
async def public_voices(db: AsyncSession = Depends(get_db)):
    voices = (await db.execute(select(Voice).where(Voice.is_public == True).order_by(Voice.id.desc()).limit(200))).scalars().all()
    return [_voice_out(v) for v in voices]


