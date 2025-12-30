from __future__ import annotations

import asyncio
import json
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse
from fastapi import Depends, Header, Request

from app.api.services.kv import KV
from app.core.config import settings
from app.tasks.jobs import run_tts_job
from app.core.responses import success_response
from app.api.services.redis_pubsub import RedisPubSub
from app.api.services.storage import to_public_file_url
from app.routers import tts_console_router as console_router
from app.routers import tts_openapi_router as openapi_router
from app.core.models import JobStatus, TTSJob, User, CloneJob, Voice
from app.core.schemas import JobOut, TTSJobOut, TTSCreatIn, Response
from app.api.services.idempotency import get_idempotency, set_idempotency
from app.core.error_codes import TTSError, VoiceError, CloneError, CreditError
from app.api.services.billing import (
    calc_cost,
    ensure_sufficient_and_consume,
    utf8_bytes,
)
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionException,
)
from app.core.deps import (
    get_db,
    OpenAPIPrincipal,
    require_console_user,
    require_openapi_principal,
)


def _tts_out(job: TTSJob) -> TTSJobOut:
    return TTSJobOut(
        id=job.uuid,
        status=job.status.value,
        error=job.error or "",
        voice_uuid=job.voice_uuid,  # 返回音色 UUID
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


async def _create_job(db: AsyncSession, user_id: int, payload: TTSCreatIn) -> TTSJob:
    """创建TTS任务，失败时抛出异常"""
    b = utf8_bytes(payload.text)
    if b > settings.max_text_utf8_bytes:
        raise BadRequestException(
            error=TTSError.TEXT_TOO_LONG,
            data={"max_bytes": settings.max_text_utf8_bytes, "current_bytes": b},
        )

    # 根据 clone_job_id 查找对应的克隆任务
    # 先尝试查找用户自己的克隆任务
    clone_job = (
        await db.execute(
            select(CloneJob).where(
                CloneJob.uuid == payload.clone_job_id,
                CloneJob.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    
    # 如果没找到，再查找公开的克隆任务（如官方音色）
    if not clone_job:
        clone_job = (
            await db.execute(
                select(CloneJob).where(
                    CloneJob.uuid == payload.clone_job_id,
                    CloneJob.is_public.is_(True),
                )
            )
        ).scalar_one_or_none()

    if not clone_job:
        raise NotFoundException(
            error=CloneError.CLONE_NOT_FOUND,
            data={"clone_job_id": payload.clone_job_id},
        )

    if clone_job.status != JobStatus.succeeded:
        raise BadRequestException(
            message="克隆任务未完成",
            error=TTSError.INVALID_TTS_PARAMS,
            data={
                "clone_job_id": payload.clone_job_id,
                "current_status": clone_job.status.value,
                "message": "请等待克隆任务完成后再创建 TTS 任务",
            },
        )

    if not clone_job.result_voice_uuid:
        raise BadRequestException(
            message="克隆任务异常：未生成音色 UUID",
            error=TTSError.INVALID_TTS_PARAMS,
            data={"clone_job_id": payload.clone_job_id},
        )

    # 使用克隆任务生成的音色 UUID
    voice_uuid = clone_job.result_voice_uuid

    # 验证音色存在且用户有权限使用
    voice = (
        await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    ).scalar_one_or_none()

    if not voice:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND, data={"voice_uuid": voice_uuid}
        )

    if voice.owner_user_id != user_id and not voice.is_public:
        raise PermissionException(
            message="无权使用该音色",
            error=VoiceError.VOICE_NOT_FOUND,
            data={"voice_uuid": voice_uuid},
        )

    speed_factor = payload.speed_factor if payload.speed_factor is not None else 1.0
    temperature = payload.temperature if payload.temperature is not None else 1.0
    top_k = payload.top_k if payload.top_k is not None else 5
    top_p = payload.top_p if payload.top_p is not None else 1.0

    cost = calc_cost(payload.text)
    job = TTSJob(
        user_id=user_id,
        voice_uuid=voice_uuid,  # 使用从克隆任务获取的 voice_uuid
        text=payload.text,
        text_utf8_bytes=b,
        cost_credits=cost,
        tags=voice.tags or [],  # 使用音色的标签
        speed_factor=speed_factor,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        webhook_url=payload.webhook_url or "",
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
        raise BadRequestException(
            error=CreditError.INSUFFICIENT_BALANCE,
            data={"required": cost, "error": str(e)},
        )

    return job


@console_router.post(
    "/tts/jobs", summary="创建 TTS 任务", response_model=Response[JobOut]
)
async def console_create_tts(
    payload: TTSCreatIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    # 创建任务（失败时抛出异常）
    job = await _create_job(db, user.id, payload)

    await db.flush()  # 确保 UUID 已生成
    # 异步：如果没有 celery broker，开发时允许直接同步跑（方便联调）
    if settings.celery_broker_url:
        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.jobs.run_tts_job", args=[job.id])
    else:
        run_tts_job(job.id)

    job_data = JobOut(id=job.uuid, status=job.status.value, error=job.error or "")
    return success_response("TTS 任务创建成功", job_data.model_dump())


@console_router.get(
    "/tts/jobs/{job_uuid}",
    summary="获取 TTS 任务详情",
    response_model=Response[TTSJobOut],
)
async def console_get_tts(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    job = (
        await db.execute(
            select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundException(
            error=TTSError.INVALID_TTS_PARAMS,
            message="任务不存在",
            data={"job_uuid": job_uuid},
        )

    tts_data = _tts_out(job)
    return success_response("获取成功", tts_data.model_dump())


@openapi_router.post(
    "/tts/jobs", summary="创建 TTS 任务", response_model=Response[JobOut]
)
async def openapi_create_tts(
    payload: TTSCreatIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    kv = KV.from_settings()
    existed = get_idempotency(
        kv, principal.user.id, "openapi:tts:create", idempotency_key
    )
    if existed:
        job_data = JobOut(id=existed, status="queued")
        return success_response("TTS 任务已存在（幂等）", job_data.model_dump())

    # 创建任务（失败时抛出异常）
    job = await _create_job(db, principal.user.id, payload)

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


@openapi_router.get(
    "/tts/jobs/{job_uuid}",
    summary="获取 TTS 任务详情",
    response_model=Response[TTSJobOut],
)
async def openapi_get_tts(
    job_uuid: str,
    db: AsyncSession = Depends(get_db),
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    job = (
        await db.execute(
            select(TTSJob).where(
                TTSJob.uuid == job_uuid, TTSJob.user_id == principal.user.id
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundException(
            error=TTSError.INVALID_TTS_PARAMS,
            message="任务不存在",
            data={"job_uuid": job_uuid},
        )

    tts_data = _tts_out(job)
    return success_response("获取成功", tts_data.model_dump())


async def _stream_tts_events(job_uuid: str, user_id: int) -> StreamingResponse:
    """
    SSE 推送 TTS 任务状态（Redis Pub/Sub + 降级轮询）

    优先使用 Redis Pub/Sub 实时推送，Redis 不可用时降级到数据库轮询
    """
    from app.core.db import AsyncSessionLocal

    async def event_generator():
        start_time = time.time()
        max_wait_seconds = getattr(settings, "tts_stream_timeout_seconds", 300)
        heartbeat_seconds = getattr(settings, "tts_stream_heartbeat_seconds", 15)
        last_heartbeat = start_time
        last_status = None

        try:
            # 1️⃣ 查询任务初始状态
            async with AsyncSessionLocal() as db:
                job = (
                    await db.execute(
                        select(TTSJob).where(
                            TTSJob.uuid == job_uuid, TTSJob.user_id == user_id
                        )
                    )
                ).scalar_one_or_none()

                if not job:
                    yield f"event: error\ndata: {json.dumps({'message': '任务不存在', 'code': 'not_found'})}\n\n"
                    return

                last_status = job.status
                status_data = {
                    "job_id": job.uuid,
                    "status": job.status.value,
                    "timestamp": time.time(),
                }
                yield f"event: status\ndata: {json.dumps(status_data)}\n\n"

            # 2️⃣ 如果已完成，直接返回结果
            if last_status in [JobStatus.succeeded, JobStatus.failed]:
                async with AsyncSessionLocal() as db:
                    job = (
                        await db.execute(select(TTSJob).where(TTSJob.uuid == job_uuid))
                    ).scalar_one()
                    tts_data = _tts_out(job)
                    complete_data = {
                        "job_id": job.uuid,
                        "status": job.status.value,
                        "data": tts_data.model_dump(),
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                return

            # 3️⃣ 尝试使用 Redis Pub/Sub（优先）
            redis_available = await RedisPubSub.get_client() is not None

            if redis_available:
                # 🚀 使用 Redis Pub/Sub 实时推送
                async for message in RedisPubSub.subscribe_job_status(
                    "tts", job_uuid, timeout=max_wait_seconds
                ):
                    # 检查超时
                    if time.time() - start_time > max_wait_seconds:
                        yield f"event: timeout\ndata: {json.dumps({'message': '任务处理超时', 'elapsed_seconds': max_wait_seconds, 'code': 'timeout'})}\n\n"
                        break

                    # 推送状态变化
                    status_data = {
                        "job_id": job_uuid,
                        "status": message.get("status"),
                        "timestamp": time.time(),
                    }
                    yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                    last_heartbeat = time.time()

                    # 终态：推送完整数据
                    if message.get("status") in ["succeeded", "failed"]:
                        async with AsyncSessionLocal() as db:
                            job = (
                                await db.execute(
                                    select(TTSJob).where(TTSJob.uuid == job_uuid)
                                )
                            ).scalar_one()
                            tts_data = _tts_out(job)
                            complete_data = {
                                "job_id": job.uuid,
                                "status": job.status.value,
                                "data": tts_data.model_dump(),
                            }
                            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                        break
            else:
                # ⚠️ 降级：使用数据库轮询（每 3 秒一次，减少压力）
                while True:
                    # 检查超时
                    if time.time() - start_time > max_wait_seconds:
                        yield f"event: timeout\ndata: {json.dumps({'message': '任务处理超时', 'elapsed_seconds': max_wait_seconds, 'code': 'timeout'})}\n\n"
                        break

                    # 等待 3 秒（降级模式下减少数据库压力）
                    try:
                        await asyncio.sleep(3)
                    except asyncio.CancelledError:
                        return

                    # 查询状态
                    try:
                        async with AsyncSessionLocal() as db:
                            job = (
                                await db.execute(
                                    select(TTSJob).where(
                                        TTSJob.uuid == job_uuid,
                                        TTSJob.user_id == user_id,
                                    )
                                )
                            ).scalar_one_or_none()
                    except asyncio.CancelledError:
                        return

                    if not job:
                        yield f"event: error\ndata: {json.dumps({'message': '任务已被删除', 'code': 'deleted'})}\n\n"
                        break

                    # 状态变化时推送
                    if job.status != last_status:
                        status_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "timestamp": time.time(),
                        }
                        yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                        last_status = job.status
                        last_heartbeat = time.time()

                    # 心跳
                    if time.time() - last_heartbeat >= heartbeat_seconds:
                        heartbeat_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "timestamp": time.time(),
                        }
                        yield f"event: ping\ndata: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = time.time()

                    # 终态：推送完整数据
                    if job.status in [JobStatus.succeeded, JobStatus.failed]:
                        tts_data = _tts_out(job)
                        complete_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "data": tts_data.model_dump(),
                        }
                        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                        break

        except asyncio.CancelledError:
            # 客户端断开连接
            return
        except Exception as e:
            import traceback

            error_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'message': error_msg, 'code': 'server_error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@console_router.get(
    "/tts/jobs/{job_uuid}/events", summary="SSE 流式推送 TTS 任务状态更新"
)
async def console_stream_tts_events(
    job_uuid: str,
    user: User = Depends(require_console_user),
):
    return await _stream_tts_events(job_uuid, user.id)


@openapi_router.get(
    "/tts/jobs/{job_uuid}/events", summary="SSE 流式推送 TTS 任务状态更新"
)
async def openapi_stream_tts_events(
    job_uuid: str,
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    return await _stream_tts_events(job_uuid, principal.user.id)
