from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_console_user
from app.models import User, Voice
from app.responses import (
    success_response,
    not_found_response,
    forbidden_response,
)
from app.schemas import VoiceOut, VoiceUpdateIn, VoiceRenameIn
from app.services.storage import to_public_file_url

console_router = APIRouter(prefix="/console", tags=["console-voices"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-voices"])


def _voice_out(v: Voice) -> VoiceOut:
    return VoiceOut(
        id=v.uuid,  # 返回 UUID 而不是数字 ID
        name=v.name,
        avatar_url=v.avatar_url,
        description=v.description,
        tags=v.tags or [],
        is_public=v.is_public,
        preview_audio_url=(
            to_public_file_url(v.preview_audio_path) if v.preview_audio_path else ""
        ),
        likes_count=v.likes_count,
        generated_chars_count=v.generated_chars_count,
        usage_count=v.usage_count,
        created_at=v.created_at.isoformat(),
    )


@console_router.get("/voices/mine")
async def my_voices(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取我的音色列表"""
    voices = (
        (
            await db.execute(
                select(Voice)
                .where(Voice.owner_user_id == user.id)
                .order_by(Voice.id.desc())
            )
        )
        .scalars()
        .all()
    )

    voices_data = [_voice_out(v).model_dump() for v in voices]
    return success_response("获取成功", voices_data)


@console_router.patch("/voices/{voice_uuid}")
async def update_voice(
    voice_uuid: str,
    payload: VoiceUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """更新音色信息"""
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=404,
            detail=not_found_response("音色不存在", {"voice_uuid": voice_uuid}),
        )
    if v.owner_user_id != user.id:
        raise HTTPException(
            status_code=403, detail=forbidden_response("无权修改该音色")
        )
    if payload.description is not None:
        v.description = payload.description
    if payload.is_public is not None:
        v.is_public = payload.is_public
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("更新成功", voice_data.model_dump())


@console_router.patch("/voices/{voice_uuid}/name")
async def rename_voice(
    voice_uuid: str,
    payload: VoiceRenameIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """修改音色名字"""
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=404,
            detail=not_found_response("音色不存在", {"voice_uuid": voice_uuid}),
        )
    if v.owner_user_id != user.id:
        raise HTTPException(
            status_code=403, detail=forbidden_response("无权修改该音色")
        )
    
    # 更新音色名字
    v.name = payload.name
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("名字修改成功", voice_data.model_dump())


@console_router.get("/voices/public")
@openapi_router.get("/voices/public")
async def public_voices(db: AsyncSession = Depends(get_db)):
    """获取公共音色列表"""
    voices = (
        (
            await db.execute(
                select(Voice)
                .where(Voice.is_public.is_(True))
                .order_by(Voice.id.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    voices_data = [_voice_out(v).model_dump() for v in voices]
    return success_response("获取成功", voices_data)


@console_router.post("/voices/{voice_uuid}/like")
async def like_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """点赞音色"""
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=404,
            detail=not_found_response("音色不存在", {"voice_uuid": voice_uuid}),
        )
    
    # 增加点赞数
    v.likes_count += 1
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("点赞成功", voice_data.model_dump())


@console_router.delete("/voices/{voice_uuid}/like")
async def unlike_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """取消点赞音色"""
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=404,
            detail=not_found_response("音色不存在", {"voice_uuid": voice_uuid}),
        )
    
    # 减少点赞数（但不能小于0）
    if v.likes_count > 0:
        v.likes_count -= 1
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("取消点赞成功", voice_data.model_dump())
