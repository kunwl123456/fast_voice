from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.deps import OpenAPIPrincipal, get_db, require_console_user, require_openapi_principal
from app.models import CloneJob, JobStatus
from app.routes.shared import get_default_project
from app.schemas import CloneCreateOut, CloneJobOut
from app.services.idempotency import get_idempotency, set_idempotency
from app.services.kv import KV
from app.services.storage import job_dir, save_bytes
from app.tasks.jobs import run_clone_job

console_router = APIRouter(prefix="/console", tags=["console-clone"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-clone"])


def _clone_out(job: CloneJob) -> CloneJobOut:
    return CloneJobOut(
        id=job.id,
        status=job.status.value,
        error=job.error or "",
        voice_name=job.voice_name,
        result_voice_id=job.result_voice_id,
    )


async def _create_clone_job(db: AsyncSession, project_id: int, voice_name: str, is_public: bool) -> CloneJob:
    job = CloneJob(
        project_id=project_id,
        voice_name=voice_name,
        is_public=is_public,
        status=JobStatus.queued,
        dataset_dir="",
    )
    db.add(job)
    await db.flush()
    return job


@console_router.post("/clone/jobs", response_model=CloneCreateOut)
async def console_create_clone(
    voice_name: str,
    is_public: bool = False,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_console_user),
):
    proj = await get_default_project(db, user)
    job = await _create_clone_job(db, proj.id, voice_name, is_public)
    ds_dir = job_dir("clone_dataset", project_id=proj.id, job_id=job.id)
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
    return CloneCreateOut(id=job.id, status=job.status.value, error=job.error or "", voice_name=job.voice_name)


@console_router.get("/clone/jobs/{job_id}", response_model=CloneJobOut)
async def console_get_clone(job_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_console_user)):
    proj = await get_default_project(db, user)
    job = (await db.execute(select(CloneJob).where(CloneJob.id == job_id, CloneJob.project_id == proj.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _clone_out(job)


@openapi_router.post("/clone/jobs", response_model=CloneCreateOut)
async def openapi_create_clone(
    voice_name: str,
    is_public: bool = False,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    kv = KV.from_settings()
    existed = get_idempotency(kv, principal.project.id, "openapi:clone:create", idempotency_key)
    if existed:
        return CloneCreateOut(id=int(existed), status="queued", voice_name=voice_name)
    job = await _create_clone_job(db, principal.project.id, voice_name, is_public)
    ds_dir = job_dir("clone_dataset", project_id=principal.project.id, job_id=job.id)
    for f in files:
        content = f.file.read()
        save_bytes(os.path.join(ds_dir, f.filename or "audio.bin"), content)
    job.dataset_dir = ds_dir
    db.add(job)
    set_idempotency(kv, principal.project.id, "openapi:clone:create", idempotency_key, str(job.id), ttl_seconds=3600)
    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.jobs.run_clone_job", args=[job.id])
    return CloneCreateOut(id=job.id, status=job.status.value, error=job.error or "", voice_name=job.voice_name)


@openapi_router.get("/clone/jobs/{job_id}", response_model=CloneJobOut)
async def openapi_get_clone(job_id: int, db: AsyncSession = Depends(get_db), principal: OpenAPIPrincipal = Depends(require_openapi_principal)):
    job = (await db.execute(select(CloneJob).where(CloneJob.id == job_id, CloneJob.project_id == principal.project.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _clone_out(job)


