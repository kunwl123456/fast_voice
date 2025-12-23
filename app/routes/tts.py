from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.deps import OpenAPIPrincipal, get_db, require_console_user, require_openapi_principal
from app.models import JobStatus, TTSJob, User
from app.routes.shared import ensure_user_owns_voice
from app.schemas import JobOut, TTSJobOut, TTSCreatIn
from app.services.billing import calc_cost, ensure_sufficient_and_consume, utf8_bytes
from app.services.idempotency import get_idempotency, set_idempotency
from app.services.kv import KV
from app.services.storage import to_public_file_url
from app.tasks.jobs import run_tts_job

console_router = APIRouter(prefix="/console", tags=["console-tts"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-tts"])


def _tts_out(job: TTSJob) -> TTSJobOut:
    return TTSJobOut(
        id=job.id,
        status=job.status.value,
        error=job.error or "",
        voice_id=job.voice_id,
        text_utf8_bytes=job.text_utf8_bytes,
        cost_credits=job.cost_credits,
        output_audio_url=to_public_file_url(job.output_audio_path) if job.output_audio_path else "",
    )


async def _create_job(db: AsyncSession, user_id: int, payload: TTSCreatIn) -> TTSJob:
    b = utf8_bytes(payload.text)
    if b > settings.max_text_utf8_bytes:
        raise HTTPException(status_code=400, detail="text_too_long")
    await ensure_user_owns_voice(db, user_id, payload.voice_id)
    cost = calc_cost(payload.text)
    job = TTSJob(
        user_id=user_id,
        voice_id=payload.voice_id,
        text=payload.text,
        text_utf8_bytes=b,
        cost_credits=cost,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()
    # 预扣费（失败会在 worker 里退款）
    try:
        await ensure_sufficient_and_consume(db=db, user_id=user_id, amount=cost, ref_type="tts", ref_id=str(job.id))
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return job


@console_router.post("/tts/jobs", response_model=JobOut)
async def console_create_tts(payload: TTSCreatIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    job = await _create_job(db, user.id, payload)
    # 异步：如果没有 celery broker，开发时允许直接同步跑（方便联调）
    if settings.celery_broker_url:
        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.jobs.run_tts_job", args=[job.id])
    else:
        run_tts_job(job.id)
    return JobOut(id=job.id, status=job.status.value, error=job.error or "")


@console_router.get("/tts/jobs/{job_id}", response_model=TTSJobOut)
async def console_get_tts(job_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    job = (await db.execute(select(TTSJob).where(TTSJob.id == job_id, TTSJob.user_id == user.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _tts_out(job)


@openapi_router.post("/tts/jobs", response_model=JobOut)
async def openapi_create_tts(
    payload: TTSCreatIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    kv = KV.from_settings()
    existed = get_idempotency(kv, principal.user.id, "openapi:tts:create", idempotency_key)
    if existed:
        return JobOut(id=int(existed), status="queued")
    job = await _create_job(db, principal.user.id, payload)
    set_idempotency(kv, principal.user.id, "openapi:tts:create", idempotency_key, str(job.id), ttl_seconds=3600)
    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.jobs.run_tts_job", args=[job.id])
    return JobOut(id=job.id, status=job.status.value, error=job.error or "")


@openapi_router.get("/tts/jobs/{job_id}", response_model=TTSJobOut)
async def openapi_get_tts(job_id: int, db: AsyncSession = Depends(get_db), principal: OpenAPIPrincipal = Depends(require_openapi_principal)):
    job = (await db.execute(select(TTSJob).where(TTSJob.id == job_id, TTSJob.user_id == principal.user.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _tts_out(job)



