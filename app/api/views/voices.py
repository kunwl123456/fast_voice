from __future__ import annotations
from typing import List
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Query

from app.core.models import User, Voice
from app.core.responses import success_response
from app.core.deps import get_db, require_console
from app.api.services.storage import to_public_file_url
from app.routers import voices_console_router as console_router
from app.routers import voices_openapi_router as openapi_router
from app.api.services.voice_tags import get_tag_categories, validate_tags
from app.core.schemas import Response, VoiceOut, VoiceUpdateIn, VoiceRenameIn
from app.core.error_codes import VoiceError
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionException,
)

logger = logging.getLogger(__name__)


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


@console_router.get(
    "/mine", summary="获取我的音色列表", response_model=Response[List[VoiceOut]]
)
async def my_voices(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console)
):
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


@console_router.patch(
    "/{voice_id}", summary="更新音色信息", response_model=Response[VoiceOut]
)
async def update_voice(
    voice_uuid: str,
    payload: VoiceUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )
    if v.owner_user_id != user.id:
        raise PermissionException(
            message="无权修改该音色", error=VoiceError.VOICE_NOT_FOUND
        )

    # 验证并更新标签
    if payload.tags is not None:
        is_valid, error_msg = validate_tags(payload.tags)
        if not is_valid:
            raise BadRequestException(
                message=error_msg, error=VoiceError.INVALID_VOICE_PARAMS
            )
        v.tags = payload.tags

    if payload.description is not None:
        v.description = payload.description
    if payload.is_public is not None:
        v.is_public = payload.is_public

    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("更新成功", voice_data.model_dump())


@console_router.patch(
    "/{voice_uuid}/name",
    summary="修改音色名字",
    response_model=Response[VoiceOut],
)
async def rename_voice(
    voice_uuid: str,
    payload: VoiceRenameIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )
    if v.owner_user_id != user.id:
        raise PermissionException(
            message="无权修改该音色", error=VoiceError.VOICE_NOT_FOUND
        )

    # 更新音色名字
    v.name = payload.name
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("名字修改成功", voice_data.model_dump())


@console_router.get(
    "/official",
    summary="获取官方音色列表",
    response_model=Response[List[VoiceOut]],
)
@openapi_router.get(
    "/official",
    summary="获取官方音色列表",
    response_model=Response[List[VoiceOut]],
)
async def official_voices(
    db: AsyncSession = Depends(get_db),
    tags: list[str] | None = Query(
        default=None, description="标签筛选，可传递多个标签"
    ),
    tagMode: str = Query(
        "or", description="标签匹配模式: or(满足任一标签), and(同时满足所有标签)"
    ),
    limit: int = Query(20, ge=1, le=100, description="每页返回数量"),
    offset: int = Query(0, ge=0, description="偏移量，用于分页"),
    orderBy: str = Query(
        "createdAt",
        description="排序字段: likes(点赞), usage(使用次数), chars(生成字符数), createdAt(创建时间)",
    ),
):
    # 先找到 autogame 用户
    autogame_user = (
        await db.execute(select(User).where(User.email == "admin@autogame.ai"))
    ).scalar_one_or_none()

    if not autogame_user:
        # 如果找不到官方账号，返回空列表
        return success_response("获取成功", [])

    # 构建基础查询
    query = select(Voice).where(Voice.owner_user_id == autogame_user.id)

    # 添加调试日志
    logger.info(f"官方音色接口 - 接收到的tags参数: {tags}, tagMode: {tagMode}")

    # 如果指定了标签，进行筛选
    if tags:
        from sqlalchemy import or_, and_, cast
        from sqlalchemy.dialects.postgresql import JSONB

        if tagMode == "and":
            # AND 模式：同时包含所有标签
            # 为每个标签创建单独的条件，然后用AND连接
            conditions = []
            for tag in tags:
                conditions.append(cast(Voice.tags, JSONB).contains([tag]))

            if conditions:
                query = query.where(and_(*conditions))
        else:
            # OR 模式：包含任一标签即可
            conditions = []
            for tag in tags:
                conditions.append(cast(Voice.tags, JSONB).contains([tag]))

            if conditions:
                query = query.where(or_(*conditions))

    # 根据 orderBy 参数选择排序方式
    if orderBy == "likes":
        # 按点赞数降序，点赞数相同则按 ID 降序
        query = query.order_by(Voice.likes_count.desc(), Voice.id.desc())
    elif orderBy == "usage":
        # 按使用次数降序
        query = query.order_by(Voice.usage_count.desc(), Voice.id.desc())
    elif orderBy == "chars":
        # 按生成字符数降序
        query = query.order_by(Voice.generated_chars_count.desc(), Voice.id.desc())
    else:  # 默认按创建时间（ID）降序
        query = query.order_by(Voice.id.desc())

    # 应用分页
    query = query.limit(limit).offset(offset)

    # 执行查询
    voices = (await db.execute(query)).scalars().all()

    voices_data = [_voice_out(v).model_dump() for v in voices]
    return success_response("获取成功", voices_data)


@console_router.get("/tags", summary="获取音色标签分类", response_model=Response[dict])
@openapi_router.get("/tags", summary="获取音色标签分类", response_model=Response[dict])
async def get_voice_tags():
    return success_response("获取成功", get_tag_categories())


@console_router.get(
    "/public",
    summary="获取公共音色列表",
    response_model=Response[List[VoiceOut]],
)
@openapi_router.get(
    "/public",
    summary="获取公共音色列表（社区角色市场）",
    response_model=Response[List[VoiceOut]],
)
async def public_voices(
    db: AsyncSession = Depends(get_db),
    tags: list[str] | None = Query(
        default=None, description="标签筛选，可传递多个标签"
    ),
    tagMode: str = Query(
        "or", description="标签匹配模式: or(满足任一标签), and(同时满足所有标签)"
    ),
    limit: int = Query(20, ge=1, le=100, description="每页返回数量"),
    offset: int = Query(0, ge=0, description="偏移量，用于分页"),
    orderBy: str = Query(
        "createdAt",
        description="排序字段: likes(点赞), usage(使用次数), chars(生成字符数), createdAt(创建时间)",
    ),
):
    # 获取官方账号，以便排除官方音色
    autogame_user = (
        await db.execute(select(User).where(User.email == "admin@autogame.ai"))
    ).scalar_one_or_none()

    # 构建查询：只返回社区用户的公开音色（排除官方音色）
    query = select(Voice).where(Voice.is_public.is_(True))

    if autogame_user:
        # 排除官方账号的音色
        query = query.where(Voice.owner_user_id != autogame_user.id)

    # 添加调试日志
    logger.info(f"社区音色接口 - 接收到的tags参数: {tags}, tagMode: {tagMode}")

    # 如果指定了标签，进行筛选
    if tags:
        from sqlalchemy import or_, and_, cast
        from sqlalchemy.dialects.postgresql import JSONB

        if tagMode == "and":
            # AND 模式：同时包含所有标签
            # 为每个标签创建单独的条件，然后用AND连接
            conditions = []
            for tag in tags:
                conditions.append(cast(Voice.tags, JSONB).contains([tag]))

            if conditions:
                query = query.where(and_(*conditions))
        else:
            # OR 模式：包含任一标签即可
            conditions = []
            for tag in tags:
                conditions.append(cast(Voice.tags, JSONB).contains([tag]))

            if conditions:
                query = query.where(or_(*conditions))

    # 根据 orderBy 参数选择排序方式
    if orderBy == "likes":
        # 按点赞数降序，点赞数相同则按 ID 降序
        query = query.order_by(Voice.likes_count.desc(), Voice.id.desc())
    elif orderBy == "usage":
        # 按使用次数降序
        query = query.order_by(Voice.usage_count.desc(), Voice.id.desc())
    elif orderBy == "chars":
        # 按生成字符数降序
        query = query.order_by(Voice.generated_chars_count.desc(), Voice.id.desc())
    else:  # 默认按创建时间（ID）降序
        query = query.order_by(Voice.id.desc())

    # 应用分页
    query = query.limit(limit).offset(offset)

    voices = (await db.execute(query)).scalars().all()

    voices_data = [_voice_out(v).model_dump() for v in voices]
    return success_response("获取成功", voices_data)


@console_router.post(
    "/{voice_uuid}/like", summary="点赞音色", response_model=Response[VoiceOut]
)
async def like_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    # 增加点赞数
    v.likes_count += 1
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("点赞成功", voice_data.model_dump())


@console_router.delete(
    "/{voice_uuid}/like", summary="取消点赞", response_model=Response[VoiceOut]
)
async def unlike_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    # 减少点赞数（但不能小于0）
    if v.likes_count > 0:
        v.likes_count -= 1
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("取消点赞成功", voice_data.model_dump())
