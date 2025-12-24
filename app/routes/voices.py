from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.responses import (
    success_response,
    not_found_response,
    forbidden_response,
)
from app.models import User, Voice
from app.deps import get_db, require_console_user
from app.services.storage import to_public_file_url
from app.schemas import Response, VoiceOut, VoiceUpdateIn, VoiceRenameIn
from app.voice_tags import get_tag_categories, validate_tags

console_router = APIRouter(prefix="/console", tags=["console-voices"])
openapi_router = APIRouter(
    prefix="/openapi",
    tags=["openapi-voices"],
)


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
        clone_job_uuid=v.clone_job_uuid or "",  # 返回克隆任务UUID
        likes_count=v.likes_count,
        generated_chars_count=v.generated_chars_count,
        usage_count=v.usage_count,
        created_at=v.created_at.isoformat(),
    )


@console_router.get("/voices/mine", response_model=Response[list[VoiceOut]])
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


@console_router.patch("/voices/{voice_id}", response_model=Response[VoiceOut])
async def update_voice(
    voice_uuid: str,
    payload: VoiceUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """更新音色信息（描述、公开状态、标签）"""
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        return not_found_response("音色不存在", {"voice_uuid": voice_uuid})
    if v.owner_user_id != user.id:
        return forbidden_response("无权修改该音色")
    
    # 验证并更新标签
    if payload.tags is not None:
        is_valid, error_msg = validate_tags(payload.tags)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        v.tags = payload.tags
    
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
        return not_found_response("音色不存在", {"voice_uuid": voice_uuid})
    if v.owner_user_id != user.id:
        return forbidden_response("无权修改该音色")

    # 更新音色名字
    v.name = payload.name
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("名字修改成功", voice_data.model_dump())


@console_router.get("/voices/official")
@openapi_router.get("/voices/official")
async def official_voices(db: AsyncSession = Depends(get_db)):
    """获取官方音色列表（autogame账号创建的音色）"""
    # 先找到 autogame 用户
    autogame_user = (
        await db.execute(select(User).where(User.email == "admin@autogame.ai"))
    ).scalar_one_or_none()

    if not autogame_user:
        # 如果找不到官方账号，返回空列表
        return success_response("获取成功", [])

    # 查询该用户创建的所有音色
    voices = (
        (
            await db.execute(
                select(Voice)
                .where(Voice.owner_user_id == autogame_user.id)
                .order_by(Voice.id.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    voices_data = [_voice_out(v).model_dump() for v in voices]
    return success_response("获取成功", voices_data)


@console_router.get("/voices/tags")
@openapi_router.get("/voices/tags")
async def get_voice_tags():
    """获取音色标签分类"""
    return success_response("获取成功", get_tag_categories())


@console_router.get("/voices/public", response_model=Response[list[VoiceOut]])
@openapi_router.get("/voices/public", response_model=Response[list[VoiceOut]])
async def public_voices(
    db: AsyncSession = Depends(get_db),
    tags: list[str] = Query(None, description="标签筛选，可传递多个标签"),
    limit: int = Query(200, ge=1, le=500, description="返回数量限制"),
):
    """
    获取公共音色列表
    
    参数：
    - tags: 标签筛选（可选），支持多个标签，满足任一标签即返回
    - limit: 返回数量限制，默认200，最大500
    
    示例：
    - /voices/public
    - /voices/public?tags=中文&tags=女
    - /voices/public?tags=青年&limit=50
    """
    query = select(Voice).where(Voice.is_public.is_(True))
    
    # 如果指定了标签，进行筛选
    if tags:
        # 对于 JSON 类型的标签字段，检查是否包含任一指定标签
        from sqlalchemy import or_, cast, String, Text
        from sqlalchemy.dialects.postgresql import JSONB
        
        # 为每个标签创建一个条件：Voice.tags 包含该标签
        conditions = []
        for tag in tags:
            # PostgreSQL: 使用 @> 操作符检查 JSON 数组是否包含元素
            # 格式: tags @> '["tag_value"]'
            conditions.append(
                cast(Voice.tags, JSONB).contains([tag])
            )
        
        # 使用 OR 连接所有条件（满足任一标签即可）
        if conditions:
            query = query.where(or_(*conditions))
    
    query = query.order_by(Voice.id.desc()).limit(limit)
    
    voices = (await db.execute(query)).scalars().all()

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
        return not_found_response("音色不存在", {"voice_uuid": voice_uuid})

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
        return not_found_response("音色不存在", {"voice_uuid": voice_uuid})

    # 减少点赞数（但不能小于0）
    if v.likes_count > 0:
        v.likes_count -= 1
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("取消点赞成功", voice_data.model_dump())
