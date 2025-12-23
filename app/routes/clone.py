from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.deps import (
    OpenAPIPrincipal,
    get_db,
    require_console_user,
    require_openapi_principal,
)
from app.models import CloneJob, JobStatus, User
from app.responses import (
    success_response,
    not_found_response,
)
from app.schemas import CloneCreateOut, CloneJobOut
from app.services.idempotency import get_idempotency, set_idempotency
from app.services.kv import KV
from app.services.storage import job_dir, save_bytes
from app.tasks.jobs import run_clone_job

console_router = APIRouter(prefix="/console", tags=["console-clone"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-clone"])


def _clone_out(job: CloneJob) -> CloneJobOut:
    return CloneJobOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_name=job.voice_name,
        result_voice_uuid=job.result_voice_uuid,
    )


async def _create_clone_job(
    db: AsyncSession, user_id: int, voice_name: str, is_public: bool
) -> CloneJob:
    job = CloneJob(
        user_id=user_id,
        voice_name=voice_name,
        is_public=is_public,
        status=JobStatus.queued,
        dataset_dir="",
    )
    db.add(job)
    await db.flush()
    return job


@console_router.post("/clone/jobs")
async def console_create_clone(
    voice_name: str = Form(...),
    is_public: bool = Form(False),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """创建克隆任务"""
    job = await _create_clone_job(db, user.id, voice_name, is_public)
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
    )
    return success_response("克隆任务创建成功", clone_data.model_dump())


@console_router.get("/clone/jobs/{job_uuid}")
async def console_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """获取克隆任务详情"""
    job = (
        await db.execute(
            select(CloneJob).where(CloneJob.uuid == job_uuid, CloneJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=404, detail=not_found_response("任务不存在", {"job_uuid": job_uuid})
        )

    clone_data = _clone_out(job)
    return success_response("获取成功", clone_data.model_dump())


@openapi_router.post("/clone/jobs")
async def openapi_create_clone(
    voice_name: str = Form(...),
    is_public: bool = Form(False),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """通过 OpenAPI 创建克隆任务"""
    kv = KV.from_settings()
    existed = get_idempotency(
        kv, principal.user.id, "openapi:clone:create", idempotency_key
    )
    if existed:
        clone_data = CloneCreateOut(
            id=existed, status="queued", voice_name=voice_name
        )
        return success_response("克隆任务已存在（幂等）", clone_data.model_dump())

    job = await _create_clone_job(db, principal.user.id, voice_name, is_public)
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
    )
    return success_response("克隆任务创建成功", clone_data.model_dump())


@openapi_router.get("/clone/jobs/{job_uuid}")
async def openapi_get_clone(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    """通过 OpenAPI 获取克隆任务详情"""
    job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == job_uuid, CloneJob.user_id == principal.user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=404, detail=not_found_response("任务不存在", {"job_uuid": job_uuid})
        )

    clone_data = _clone_out(job)
    return success_response("获取成功", clone_data.model_dump())
