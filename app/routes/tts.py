from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.responses import (
    success_response,
    error_response,
    not_found_response,
    bad_request_response,
)
from app.services.kv import KV
from app.core.config import settings
from app.tasks.jobs import run_tts_job
from app.models import JobStatus, TTSJob, User
from app.services.storage import to_public_file_url
from app.routes.shared import ensure_user_owns_voice
from app.schemas import JobOut, TTSJobOut, TTSCreatIn
from app.services.idempotency import get_idempotency, set_idempotency
from app.services.billing import calc_cost, ensure_sufficient_and_consume, utf8_bytes
from app.deps import (
    OpenAPIPrincipal,
    get_db,
    require_console_user,
    require_openapi_principal,
)


console_router = APIRouter(prefix="/console", tags=["console-tts"])
openapi_router = APIRouter(prefix="/openapi", tags=["openapi-tts"])
DEFAULT_TTS_TAGS = ["default"]


def _tts_out(job: TTSJob) -> TTSJobOut:
    return TTSJobOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_id=job.voice_id,
        text_utf8_bytes=job.text_utf8_bytes,
        cost_credits=job.cost_credits,
        tags=job.tags or [],
        speed_factor=job.speed_factor,
        temperature=job.temperature,
        top_k=job.top_k,
        top_p=job.top_p,
        output_audio_url=(
            to_public_file_url(job.output_audio_path) if job.output_audio_path else ""
        ),
    )


async def _create_job(
    db: AsyncSession, user_id: int, payload: TTSCreatIn
) -> TTSJob | JSONResponse | None:
    """创建TTS任务，如果失败返回错误响应"""
    b = utf8_bytes(payload.text)
    if b > settings.max_text_utf8_bytes:
        return bad_request_response(
            "文本过长", {"max_bytes": settings.max_text_utf8_bytes, "current_bytes": b}
        )

    try:
        await ensure_user_owns_voice(db, user_id, payload.voice_id)
    except HTTPException:
        return not_found_response("音色不存在", {"voice_id": payload.voice_id})

    tags = [t.strip() for t in (payload.tags or []) if t and t.strip()]
    if not tags:
        tags = DEFAULT_TTS_TAGS

    speed_factor = payload.speed_factor if payload.speed_factor is not None else 1.0
    temperature = payload.temperature if payload.temperature is not None else 1.0
    top_k = payload.top_k if payload.top_k is not None else 5
    top_p = payload.top_p if payload.top_p is not None else 1.0

    cost = calc_cost(payload.text)
    job = TTSJob(
        user_id=user_id,
        voice_id=payload.voice_id,
        text=payload.text,
        text_utf8_bytes=b,
        cost_credits=cost,
        tags=tags,
        speed_factor=speed_factor,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()

    # 预扣费（失败会在 worker 里退款）
    try:
        await ensure_sufficient_and_consume(
            db=db, user_id=user_id, amount=cost, ref_type="tts", ref_id=str(job.id)
        )
    except ValueError as e:
        return error_response("积分不足", {"required": cost, "error": str(e)})

    return job


@console_router.post("/tts/jobs")
async def console_create_tts(
    payload: TTSCreatIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """创建 TTS 任务"""
    result = await _create_job(db, user.id, payload)
    if not isinstance(result, TTSJob):
        return result  # 返回错误响应

    job = result
    await db.flush()  # 确保 UUID 已生成
    # 异步：如果没有 celery broker，开发时允许直接同步跑（方便联调）
    if settings.celery_broker_url:
        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.jobs.run_tts_job", args=[job.id])
    else:
        run_tts_job(job.id)

    job_data = JobOut(id=job.uuid, status=job.status.value, error=job.error or "")
    return success_response("TTS 任务创建成功", job_data.model_dump())


@console_router.get("/tts/jobs/{job_uuid}")
async def console_get_tts(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """获取 TTS 任务详情"""
    job = (
        await db.execute(
            select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not job:
        return not_found_response("任务不存在", {"job_uuid": job_uuid})

    tts_data = _tts_out(job)
    return success_response("获取成功", tts_data.model_dump())


@openapi_router.post("/tts/jobs")
async def openapi_create_tts(
    payload: TTSCreatIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """通过 OpenAPI 创建 TTS 任务"""
    kv = KV.from_settings()
    existed = get_idempotency(
        kv, principal.user.id, "openapi:tts:create", idempotency_key
    )
    if existed:
        job_data = JobOut(id=existed, status="queued")
        return success_response("TTS 任务已存在（幂等）", job_data.model_dump())

    result = await _create_job(db, principal.user.id, payload)
    if not isinstance(result, TTSJob):
        return result  # 返回错误响应

    job = result
    await db.flush()  # 确保 UUID 已生成
    set_idempotency(
        kv,
        principal.user.id,
        "openapi:tts:create",
        idempotency_key,
        job.uuid,
        ttl_seconds=3600,
    )
    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.jobs.run_tts_job", args=[job.id])

    job_data = JobOut(id=job.uuid, status=job.status.value, error=job.error or "")
    return success_response("TTS 任务创建成功", job_data.model_dump())


@openapi_router.get("/tts/jobs/{job_uuid}")
async def openapi_get_tts(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    """通过 OpenAPI 获取 TTS 任务详情"""
    job = (
        await db.execute(
            select(TTSJob).where(
                TTSJob.uuid == job_uuid, TTSJob.user_id == principal.user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        return not_found_response("任务不存在", {"job_uuid": job_uuid})

    tts_data = _tts_out(job)
    return success_response("获取成功", tts_data.model_dump())
