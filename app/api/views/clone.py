from __future__ import annotations

import os
import json
import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, File, Form, Header, UploadFile

from app.api.services.kv import KV
from app.core.config import settings
from app.tasks.jobs import run_clone_job
from app.core.error_codes import CloneError
from app.core.models import CloneJob, User
from app.core.constants import JobStatus
from app.core.responses import success_response
from app.api.services.voice_tags import validate_tags
from app.routers import clone_console_router as console_router
from app.routers import clone_openapi_router as openapi_router
from app.api.services.storage import job_dir, to_public_file_url
from app.core.schemas import CloneCreateOut, CloneJobOut, Response
from app.api.services.clone_limit_checker import check_clone_limit
from app.core.exceptions import BadRequestException, NotFoundException
from app.api.services.idempotency import get_idempotency, set_idempotency
from app.core.deps import (
    get_db,
    OpenAPIPrincipal,
    require_console,
    require_openapi,
)


def _clone_out(job: CloneJob, user_uuid: str) -> CloneJobOut:
    # 构建预览音频URL
    preview_url = ""
    if job.result_voice_uuid and job.dataset_dir:
        # 预览音频路径通常在 clone 输出目录下
        preview_path = os.path.join(
            job_dir("clone", user_id=job.user_id, job_uuid=job.uuid), "preview.wav"
        )
        if os.path.exists(preview_path):
            preview_url = to_public_file_url(preview_path)

    return CloneJobOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_name=job.voice_name,
        avatar_url=job.avatar_url,
        description=job.description,
        tags=job.tags or [],
        user_id=user_uuid,
        created_at=job.created_at.isoformat(),
        preview_audio_url=preview_url,
        result_voice_uuid=job.result_voice_uuid,
    )


async def _validate_audio_file(file: UploadFile) -> None:
    """异步验证音频文件格式和大小，失败时抛出异常"""
    # 验证文件名
    if not file.filename:
        raise BadRequestException(
            message="文件名不能为空", error=CloneError.INVALID_AUDIO_FORMAT
        )

    # 验证文件格式
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.supported_audio_formats:
        raise BadRequestException(
            message=f"不支持的文件格式，仅支持：{', '.join(settings.supported_audio_formats)}",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )

    # 验证文件大小（通过 Content-Length 头）
    if file.size and file.size > settings.max_audio_file_size_bytes:
        raise BadRequestException(
            message=f"文件大小超过限制（最大 {settings.max_audio_file_size_mb}MB）",
            error=CloneError.AUDIO_TOO_LONG,
        )

    # 异步读取文件头部，确保文件可读且不为空
    try:
        # 读取前几个字节检查文件是否有效
        header_bytes = await file.read(16)
        # 重置文件指针
        await file.seek(0)

        if not header_bytes:
            raise BadRequestException(
                message="音频文件内容为空", error=CloneError.INVALID_AUDIO_FORMAT
            )
    except Exception as e:
        if isinstance(e, BadRequestException):
            raise
        raise BadRequestException(
            message=f"验证音频文件时出错: {str(e)}",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )


async def _validate_avatar_file(file: UploadFile) -> None:
    """异步验证头像文件格式和大小，失败时抛出异常"""
    # 验证文件名
    if not file.filename:
        raise BadRequestException(
            message="头像文件名不能为空", error=CloneError.INVALID_AUDIO_FORMAT
        )

    # 验证文件格式（支持常见图片格式）
    file_ext = os.path.splitext(file.filename)[1].lower()
    supported_image_formats = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    if file_ext not in supported_image_formats:
        raise BadRequestException(
            message=f"不支持的图片格式，仅支持：{', '.join(supported_image_formats)}",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )

    # 验证文件大小（限制为5MB）
    max_avatar_size = 5 * 1024 * 1024  # 5MB
    if file.size and file.size > max_avatar_size:
        raise BadRequestException(
            message="头像文件大小超过限制（最大 5MB）",
            error=CloneError.AUDIO_TOO_LONG,
        )

    # 异步读取文件头部，验证真实文件类型（magic bytes）
    try:
        # 读取前16字节用于识别文件类型
        header_bytes = await file.read(16)
        # 重置文件指针，以便后续保存时能完整读取
        await file.seek(0)

        # 验证文件magic bytes
        if not header_bytes:
            raise BadRequestException(
                message="文件内容为空", error=CloneError.INVALID_AUDIO_FORMAT
            )

        # 检查各种图片格式的magic bytes
        is_valid_image = False

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if header_bytes[:8] == b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A":
            is_valid_image = True
        # JPEG: FF D8 FF
        elif header_bytes[:3] == b"\xFF\xD8\xFF":
            is_valid_image = True
        # GIF: 47 49 46 38 (GIF8)
        elif header_bytes[:4] in [b"GIF87a", b"GIF89a"]:
            is_valid_image = True
        # WebP: 52 49 46 46 ... 57 45 42 50 (RIFF...WEBP)
        elif header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
            is_valid_image = True

        if not is_valid_image:
            raise BadRequestException(
                message="文件不是有效的图片格式",
                error=CloneError.INVALID_AUDIO_FORMAT,
            )

    except Exception as e:
        if isinstance(e, BadRequestException):
            raise
        raise BadRequestException(
            message=f"验证头像文件时出错: {str(e)}",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )


async def _save_upload_file_async(file: UploadFile, dest_path: str) -> None:
    """异步流式保存上传文件，避免阻塞事件循环"""
    # 确保目录存在
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # 流式保存，同时检查文件大小
    total_size = 0
    async with aiofiles.open(dest_path, "wb") as out:
        while chunk := await file.read(8192):  # 每次读取 8KB
            total_size += len(chunk)
            # 再次验证文件大小（防止客户端伪造 Content-Length）
            if total_size > settings.max_audio_file_size_bytes:
                # 删除已保存的部分文件
                await out.close()
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                raise ValueError(
                    f"文件大小超过限制（最大 {settings.max_audio_file_size_mb}MB）"
                )
            await out.write(chunk)


async def _save_avatar_file_async(file: UploadFile, user_id: int, job_uuid: str) -> str:
    """异步保存头像文件并返回公开URL"""
    # 获取文件扩展名
    file_ext = os.path.splitext(file.filename or "avatar.jpg")[1].lower()

    # 保存路径：使用 clone job 目录
    avatar_dir = job_dir("clone", user_id=user_id, job_uuid=job_uuid)
    os.makedirs(avatar_dir, exist_ok=True)

    avatar_filename = f"avatar{file_ext}"
    avatar_path = os.path.join(avatar_dir, avatar_filename)

    # 流式保存，同时检查文件大小
    max_avatar_size = 5 * 1024 * 1024  # 5MB
    total_size = 0
    async with aiofiles.open(avatar_path, "wb") as out:
        while chunk := await file.read(8192):  # 每次读取 8KB
            total_size += len(chunk)
            # 再次验证文件大小（防止客户端伪造 Content-Length）
            if total_size > max_avatar_size:
                # 删除已保存的部分文件
                await out.close()
                if os.path.exists(avatar_path):
                    os.remove(avatar_path)
                raise ValueError("头像文件大小超过限制（最大 5MB）")
            await out.write(chunk)

    # 返回公开访问URL
    return to_public_file_url(avatar_path)


async def _create_clone_job(
    db: AsyncSession,
    user_id: int,
    voice_name: str,
    avatar_url: str,
    description: str,
    tags: list[str],
    is_public: bool,
    remove_background_noise: bool,
) -> CloneJob:
    job = CloneJob(
        user_id=user_id,
        voice_name=voice_name,
        avatar_url=avatar_url,
        description=description,
        tags=tags,
        is_public=is_public,
        remove_background_noise=remove_background_noise,
        status=JobStatus.queued,
        dataset_dir="",
    )
    db.add(job)
    await db.flush()
    return job


@console_router.post(
    "/jobs",
    summary="创建音色克隆任务",
    response_model=Response[CloneCreateOut],
)
async def console_create_clone(
    voice_name: str = Form(...),
    avatar_file: UploadFile | None = File(None),  # 头像文件（可选）
    description: str = Form(""),
    tags: str = Form("[]"),  # JSON 字符串数组
    is_public: bool = Form(False),
    remove_background_noise: bool = Form(False),
    audio_file: UploadFile = File(...),  # 单个音频文件
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    # 步骤1：检查克隆位限制
    await check_clone_limit(db, user)

    # 步骤2：验证音频文件
    await _validate_audio_file(audio_file)

    # 验证头像文件（如果提供）
    if avatar_file and avatar_file.filename:
        await _validate_avatar_file(avatar_file)

    # 解析标签
    try:
        tags_list = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        raise BadRequestException(
            message="标签格式错误，必须是JSON数组",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )

    # 验证标签
    is_valid, error_msg = validate_tags(tags_list)
    if not is_valid:
        raise BadRequestException(
            message=error_msg, error=CloneError.INVALID_AUDIO_FORMAT
        )

    job = await _create_clone_job(
        db,
        user.id,
        voice_name,
        "",  # avatar_url 先留空，稍后上传文件后更新
        description,
        tags_list,
        is_public,
        remove_background_noise,
    )
    await db.flush()  # 确保 UUID 已生成

    # 处理头像文件上传
    avatar_url = ""
    if avatar_file and avatar_file.filename:
        try:
            avatar_url = await _save_avatar_file_async(avatar_file, user.id, job.uuid)
            job.avatar_url = avatar_url
        except ValueError as e:
            # 头像文件上传失败，删除任务
            await db.delete(job)
            await db.commit()
            raise BadRequestException(
                message=str(e), error=CloneError.INVALID_AUDIO_FORMAT
            )

    ds_dir = job_dir("clone_dataset", user_id=user.id, job_uuid=job.uuid)

    # 异步流式保存文件，避免阻塞事件循环
    dest_path = os.path.join(ds_dir, audio_file.filename or "audio.bin")
    try:
        await _save_upload_file_async(audio_file, dest_path)
    except ValueError as e:
        # 文件大小超限，删除任务
        await db.delete(job)
        await db.commit()
        raise BadRequestException(message=str(e), error=CloneError.AUDIO_TOO_LONG)

    job.dataset_dir = ds_dir
    db.add(job)
    # 异步：如果没有 celery broker，开发时允许直接同步跑
    if settings.celery_broker_url:
        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.jobs.run_clone_job", args=[job.id])
    else:
        run_clone_job(job.id)

    clone_data = CloneCreateOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_name=job.voice_name,
        avatar_url=job.avatar_url,
        description=job.description,
        tags=job.tags or [],
        user_id=user.uuid,
        created_at=job.created_at.isoformat(),
        preview_audio_url="",  # 创建时还没有预览音频
    )
    return success_response("克隆任务创建成功", clone_data.model_dump())


@console_router.get(
    "/jobs/{job_uuid}",
    summary="获取音色克隆任务详情",
    response_model=Response[CloneJobOut],
)
async def console_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == job_uuid, CloneJob.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundException(
            error=CloneError.CLONE_NOT_FOUND, data={"job_uuid": job_uuid}
        )

    clone_data = _clone_out(job, user.uuid)
    return success_response("获取成功", clone_data.model_dump())


@openapi_router.post(
    "/jobs", summary="创建音色克隆任务", response_model=Response[CloneCreateOut]
)
async def openapi_create_clone(
    voice_name: str = Form(...),
    avatar_file: UploadFile | None = File(None),  # 头像文件（可选）
    description: str = Form(""),
    tags: str = Form("[]"),  # JSON 字符串数组
    is_public: bool = Form(False),
    remove_background_noise: bool = Form(False),
    audio_file: UploadFile = File(...),  # 单个音频文件
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    # 步骤1：检查克隆位限制
    await check_clone_limit(db, principal.user)

    # 步骤2：验证音频文件
    await _validate_audio_file(audio_file)

    # 验证头像文件（如果提供）
    if avatar_file and avatar_file.filename:
        await _validate_avatar_file(avatar_file)

    # 解析标签
    try:
        tags_list = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        raise BadRequestException(
            message="标签格式错误，必须是JSON数组",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )

    # 验证标签
    is_valid, error_msg = validate_tags(tags_list)
    if not is_valid:
        raise BadRequestException(
            message=error_msg, error=CloneError.INVALID_AUDIO_FORMAT
        )

    kv = KV.from_settings()
    existed = get_idempotency(
        kv, principal.user.id, "openapi:clone:create", idempotency_key
    )
    if existed:
        # 幂等返回需要查询任务详情
        job = (
            await db.execute(select(CloneJob).where(CloneJob.uuid == existed))
        ).scalar_one_or_none()
        if job:
            clone_data = _clone_out(job, principal.user.uuid)
            return success_response("克隆任务已存在（幂等）", clone_data.model_dump())

    job = await _create_clone_job(
        db,
        principal.user.id,
        voice_name,
        "",  # avatar_url 先留空，稍后上传文件后更新
        description,
        tags_list,
        is_public,
        remove_background_noise,
    )
    await db.flush()  # 确保 UUID 已生成

    # 处理头像文件上传
    avatar_url = ""
    if avatar_file and avatar_file.filename:
        try:
            avatar_url = await _save_avatar_file_async(
                avatar_file, principal.user.id, job.uuid
            )
            job.avatar_url = avatar_url
        except ValueError as e:
            # 头像文件上传失败，删除任务
            await db.delete(job)
            await db.commit()
            raise BadRequestException(
                message=str(e), error=CloneError.INVALID_AUDIO_FORMAT
            )

    ds_dir = job_dir("clone_dataset", user_id=principal.user.id, job_uuid=job.uuid)

    # 异步流式保存文件，避免阻塞事件循环
    dest_path = os.path.join(ds_dir, audio_file.filename or "audio.bin")
    try:
        await _save_upload_file_async(audio_file, dest_path)
    except ValueError as e:
        # 文件大小超限，删除任务
        await db.delete(job)
        await db.commit()
        raise BadRequestException(message=str(e), error=CloneError.AUDIO_TOO_LONG)

    job.dataset_dir = ds_dir
    db.add(job)
    set_idempotency(
        kv,
        principal.user.id,
        "openapi:clone:create",
        idempotency_key,
        job.uuid,
        ttl_seconds=3600,
    )
    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.jobs.run_clone_job", args=[job.id])

    clone_data = CloneCreateOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_name=job.voice_name,
        avatar_url=job.avatar_url,
        description=job.description,
        tags=job.tags or [],
        user_id=principal.user.uuid,
        created_at=job.created_at.isoformat(),
        preview_audio_url="",  # 创建时还没有预览音频
    )
    return success_response("克隆任务创建成功", clone_data.model_dump())


@openapi_router.get(
    "/jobs/{job_uuid}",
    summary="获取音色克隆任务详情",
    response_model=Response[CloneJobOut],
)
async def openapi_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi),
):
    job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == job_uuid, CloneJob.user_id == principal.user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundException(
            error=CloneError.CLONE_NOT_FOUND, data={"job_uuid": job_uuid}
        )

    clone_data = _clone_out(job, principal.user.uuid)
    return success_response("获取成功", clone_data.model_dump())
