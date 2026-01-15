from __future__ import annotations
from typing import List
import logging
import os
from pathlib import Path as PathLib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Query, Path, File, UploadFile

from app.core.models import User, Voice, TTSJob, JobStatus
from app.core.responses import success_response
from app.core.deps import get_db, require_console, require_openapi, OpenAPIPrincipal
from app.api.services.storage import (
    to_public_file_url,
    data_dir,
    ensure_dir,
    save_bytes,
)
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


def _validate_voice_avatar_file(
    content_type: str | None, filename: str | None, content: bytes
) -> str:
    """
    验证音色头像文件

    ### 参数
    - content_type: 文件 Content-Type
    - filename: 文件名
    - content: 文件内容

    ### 返回
    - 文件扩展名

    ### 异常
    - BadRequestException: 文件格式不支持或文件过大
    """
    # 验证文件类型
    if not content_type or not content_type.startswith("image/"):
        raise BadRequestException(
            message="文件类型必须是图片",
            error=VoiceError.INVALID_VOICE_PARAMS,
        )

    # 支持的图片扩展名
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    file_ext = PathLib(filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        raise BadRequestException(
            message=f"不支持的图片格式，仅支持：{', '.join(allowed_extensions)}",
            error=VoiceError.INVALID_VOICE_PARAMS,
        )

    # 验证大小（5MB限制）
    if len(content) > 5 * 1024 * 1024:
        raise BadRequestException(
            message="头像文件大小不能超过 5MB",
            error=VoiceError.INVALID_VOICE_PARAMS,
        )

    if len(content) == 0:
        raise BadRequestException(
            message="文件内容为空",
            error=VoiceError.INVALID_VOICE_PARAMS,
        )

    return file_ext


def _voice_out(v: Voice, is_official: bool = False) -> VoiceOut:
    """
    将 Voice 模型转换为 VoiceOut schema
    
    Args:
        v: Voice 模型实例
        is_official: 是否为官方音色。如果是，将 description 从 "|" 分隔格式转换为多语言 map
    
    Returns:
        VoiceOut schema 实例
    """
    # 处理 description：如果是官方音色，将 "|" 分隔的字符串转换为多语言 map
    description: dict[str, str] | str = v.description
    if is_official and v.description:
        # 格式：简体|繁体|日语|韩语|英语
        parts = v.description.split("|")
        if len(parts) == 5:
            description = {
                "zh": parts[0].strip(),      # 简体中文
                "zh_tw": parts[1].strip(),   # 繁体中文
                "jp": parts[2].strip(),      # 日语
                "ko": parts[3].strip(),      # 韩语
                "en": parts[4].strip(),      # 英语
            }
        # 如果格式不对，保持原字符串
    
    return VoiceOut(
        id=v.uuid,  # 返回 UUID 而不是数字 ID
        name=v.name,
        avatar_url=v.avatar_url,
        description=description,
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
    payload: VoiceUpdateIn,
    voice_uuid: str = Path(..., alias="voice_id"),
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


@console_router.post(
    "/{voice_uuid}/avatar/upload",
    summary="上传音色头像",
    response_model=Response[VoiceOut],
)
async def upload_voice_avatar(
    voice_uuid: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    """
    上传音色头像图片

    ### 功能说明
    - 上传图片文件作为音色头像
    - 自动保存到服务器并生成访问 URL
    - 更新音色头像地址

    ### 文件要求
    - **支持格式**: JPG, JPEG, PNG, GIF, WebP
    - **文件大小**: 最大 5MB
    - **Content-Type**: 必须是 `image/*` 类型

    ### 存储规则
    - 文件保存路径：`data/voice_avatars/{voice_uuid}.{ext}`
    - 旧头像会被新上传的图片覆盖

    ### 权限要求
    - 只有音色拥有者可以上传头像
    """
    # 查找音色
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    # 权限检查：只有音色拥有者可以修改
    if v.owner_user_id != user.id:
        raise PermissionException(
            message="无权修改该音色", error=VoiceError.VOICE_NOT_FOUND
        )

    # 读取文件内容
    content = await file.read()

    # 验证文件（如有问题会抛出异常）
    file_ext = _validate_voice_avatar_file(file.content_type, file.filename, content)

    # 保存文件到 data/voice_avatars/{voice_uuid}{ext}
    avatars_dir = ensure_dir(os.path.join(data_dir(), "voice_avatars"))
    avatar_filename = f"{voice_uuid}{file_ext}"
    avatar_path = os.path.join(avatars_dir, avatar_filename)
    save_bytes(avatar_path, content)

    # 生成公开访问URL
    avatar_url = to_public_file_url(avatar_path)

    # 更新音色头像
    v.avatar_url = avatar_url
    db.add(v)
    await db.flush()

    voice_data = _voice_out(v)
    return success_response("音色头像上传成功", voice_data.model_dump())


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
        "likes",
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

    # 官方音色的 description 需要转换为多语言 map 格式
    voices_data = [_voice_out(v, is_official=True).model_dump() for v in voices]
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
        "likes",
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


def _delete_voice_files(v: Voice) -> None:
    """
    删除音色相关的文件（预览音频和头像）
    
    ### 参数
    - v: Voice 对象
    """
    # 删除预览音频文件（如果存在）
    if v.preview_audio_path and os.path.exists(v.preview_audio_path):
        try:
            os.remove(v.preview_audio_path)
        except Exception as e:
            logger.warning(f"删除预览音频文件失败: {v.preview_audio_path}, 错误: {e}")

    # 删除头像文件（如果存在）
    # 头像文件路径格式：data/voice_avatars/{voice_uuid}.{ext}
    if v.avatar_url:
        try:
            # 从公开URL提取本地路径
            # avatar_url 格式: /files/voice_avatars/{voice_uuid}.{ext}
            if v.avatar_url.startswith("/files/"):
                relative_path = v.avatar_url[len("/files/") :]
                avatar_path = os.path.join(data_dir(), relative_path)
                if os.path.exists(avatar_path):
                    os.remove(avatar_path)
        except Exception as e:
            logger.warning(f"删除头像文件失败: {v.avatar_url}, 错误: {e}")


@console_router.delete(
    "/{voice_uuid}", summary="删除音色", response_model=Response[dict]
)
async def console_delete_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    """
    删除音色数据（Console 版本）

    ### 功能说明
    - 删除指定的音色及其相关文件
    - 支持通过音色 UUID 或克隆任务 UUID 删除
    - 只有音色拥有者可以删除
    - 会删除预览音频文件和头像文件（如果存在）

    ### 权限要求
    - 需要 Console 认证（Bearer Token）
    - 只有音色拥有者可以删除

    ### 参数说明
    - voice_uuid: 可以是音色的 UUID，也可以是克隆任务的 UUID（clone_job_uuid）
    """
    # 先尝试通过音色 UUID 查找
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    
    # 如果没找到，尝试通过克隆任务 UUID 查找
    if not v:
        v = (
            await db.execute(
                select(Voice).where(Voice.clone_job_uuid == voice_uuid)
            )
        ).scalar_one_or_none()
    
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    # 权限检查：只有音色拥有者可以删除
    if v.owner_user_id != user.id:
        raise PermissionException(
            message="无权删除该音色", error=VoiceError.VOICE_NOT_FOUND
        )

    # 检查是否有正在运行中的 TTS 任务（queued 或 running 状态）
    active_tts_jobs = (
        await db.execute(
            select(TTSJob).where(
                TTSJob.voice_uuid == v.uuid,
                TTSJob.status.in_([JobStatus.queued, JobStatus.running])
            )
        )
    ).scalars().all()
    
    if active_tts_jobs:
        raise BadRequestException(
            message=f"该音色正在被 {len(active_tts_jobs)} 个 TTS 任务使用（进行中），无法删除。请等待任务完成后再删除。",
            error=VoiceError.VOICE_IN_USE,
        )
    
    # 注意：已完成的 TTS 任务记录会自动保留，voice_uuid 会被数据库自动设置为 NULL
    # （通过外键约束 ON DELETE SET NULL）
    # 音频文件也会保留，因为它们是用户已付费生成的资源

    # 删除相关文件
    _delete_voice_files(v)

    # 删除数据库记录
    await db.delete(v)
    await db.commit()

    return success_response("删除成功", {"voice_uuid": v.uuid})


@openapi_router.delete(
    "/{voice_uuid}", summary="删除音色", response_model=Response[dict]
)
async def openapi_delete_voice(
    voice_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi),
):
    """
    删除音色数据（OpenAPI 版本）

    ### 功能说明
    - 删除指定的音色及其相关文件
    - 支持通过音色 UUID 或克隆任务 UUID 删除
    - 只有音色拥有者可以删除
    - 会删除预览音频文件和头像文件（如果存在）

    ### 权限要求
    - 需要 OpenAPI 认证（API Key）
    - 只有音色拥有者可以删除

    ### 参数说明
    - voice_uuid: 可以是音色的 UUID，也可以是克隆任务的 UUID（clone_job_uuid）
    """
    # 先尝试通过音色 UUID 查找
    v = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()
    
    # 如果没找到，尝试通过克隆任务 UUID 查找
    if not v:
        v = (
            await db.execute(
                select(Voice).where(Voice.clone_job_uuid == voice_uuid)
            )
        ).scalar_one_or_none()
    
    if not v:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    # 权限检查：只有音色拥有者可以删除
    if v.owner_user_id != principal.user.id:
        raise PermissionException(
            message="无权删除该音色", error=VoiceError.VOICE_NOT_FOUND
        )

    # 检查是否有正在运行中的 TTS 任务（queued 或 running 状态）
    active_tts_jobs = (
        await db.execute(
            select(TTSJob).where(
                TTSJob.voice_uuid == v.uuid,
                TTSJob.status.in_([JobStatus.queued, JobStatus.running])
            )
        )
    ).scalars().all()
    
    if active_tts_jobs:
        raise BadRequestException(
            message=f"该音色正在被 {len(active_tts_jobs)} 个 TTS 任务使用（进行中），无法删除。请等待任务完成后再删除。",
            error=VoiceError.VOICE_IN_USE,
        )
    
    # 注意：已完成的 TTS 任务记录会自动保留，voice_uuid 会被数据库自动设置为 NULL
    # （通过外键约束 ON DELETE SET NULL）
    # 音频文件也会保留，因为它们是用户已付费生成的资源

    # 删除相关文件
    _delete_voice_files(v)

    # 删除数据库记录
    await db.delete(v)
    await db.commit()

    return success_response("删除成功", {"voice_uuid": v.uuid})
