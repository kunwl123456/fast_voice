from __future__ import annotations

import os
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, File, Form, Header, UploadFile

from app.services.kv import KV
from app.core.config import settings
from app.tasks.jobs import run_clone_job
from app.voice_tags import validate_tags
from app.models import CloneJob, JobStatus, User
from app.responses import (
    success_response,
    not_found_response,
    bad_request_response,
)
from app.deps import (
    get_db,
    OpenAPIPrincipal,
    require_console_user,
    require_openapi_principal,
)
from app.schemas import CloneCreateOut, CloneJobOut, Response
from app.services.idempotency import get_idempotency, set_idempotency
from app.services.storage import job_dir, save_bytes, to_public_file_url

console_router = APIRouter(prefix="/console", tags=["音色克隆"])
openapi_router = APIRouter(prefix="/openapi", tags=["音色克隆"])


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
    "/clone/jobs",
    summary="创建音色克隆任务",
    response_model=Response[CloneCreateOut],
)
async def console_create_clone(
    voice_name: str = Form(...),
    avatar_url: str = Form(""),
    description: str = Form(""),
    tags: str = Form("[]"),  # JSON 字符串数组
    is_public: bool = Form(False),
    remove_background_noise: bool = Form(False),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    # 解析标签
    try:
        tags_list = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        return bad_request_response("标签格式错误，必须是JSON数组")

    # 验证标签
    is_valid, error_msg = validate_tags(tags_list)
    if not is_valid:
        return bad_request_response(error_msg)

    job = await _create_clone_job(
        db,
        user.id,
        voice_name,
        avatar_url,
        description,
        tags_list,
        is_public,
        remove_background_noise,
    )
    await db.flush()  # 确保 UUID 已生成
    ds_dir = job_dir("clone_dataset", user_id=user.id, job_uuid=job.uuid)
    for f in files:
        content = f.file.read()
        save_bytes(os.path.join(ds_dir, f.filename or "audio.bin"), content)
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
    "/clone/jobs/{job_uuid}",
    summary="获取音色克隆任务详情",
    response_model=Response[CloneJobOut],
)
async def console_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == job_uuid, CloneJob.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        return not_found_response("任务不存在", {"job_uuid": job_uuid})

    clone_data = _clone_out(job, user.uuid)
    return success_response("获取成功", clone_data.model_dump())


@openapi_router.post(
    "/clone/jobs", summary="创建音色克隆任务", response_model=Response[CloneCreateOut]
)
async def openapi_create_clone(
    voice_name: str = Form(...),
    avatar_url: str = Form(""),
    description: str = Form(""),
    tags: str = Form("[]"),  # JSON 字符串数组
    is_public: bool = Form(False),
    remove_background_noise: bool = Form(False),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):

    # 解析标签
    try:
        tags_list = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        return bad_request_response("标签格式错误，必须是JSON数组")

    # 验证标签
    is_valid, error_msg = validate_tags(tags_list)
    if not is_valid:
        return bad_request_response(error_msg)

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
        avatar_url,
        description,
        tags_list,
        is_public,
        remove_background_noise,
    )
    await db.flush()  # 确保 UUID 已生成
    ds_dir = job_dir("clone_dataset", user_id=principal.user.id, job_uuid=job.uuid)
    for f in files:
        content = f.file.read()
        save_bytes(os.path.join(ds_dir, f.filename or "audio.bin"), content)
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
    "/clone/jobs/{job_uuid}",
    summary="获取音色克隆任务详情",
    response_model=Response[CloneJobOut],
)
async def openapi_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == job_uuid, CloneJob.user_id == principal.user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        return not_found_response("任务不存在", {"job_uuid": job_uuid})

    clone_data = _clone_out(job, principal.user.uuid)
    return success_response("获取成功", clone_data.model_dump())
