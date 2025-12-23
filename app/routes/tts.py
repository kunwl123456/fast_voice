from __future__ import annotations

import asyncio
import json
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, StreamingResponse
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


@console_router.get("/tts/jobs/{job_uuid}/events")
async def console_stream_tts_events(
    job_uuid: str,
    user: User = Depends(require_console_user),
):
    """
    通过 SSE 流式推送 TTS 任务状态更新
    
    返回格式：
    - event: status - 状态变化事件
    - event: complete - 任务完成事件（成功或失败）
    - event: error - 错误事件
    - event: timeout - 超时事件
    """
    async def event_generator():
        from app.db import AsyncSessionLocal  # 导入 session 工厂
        
        last_status = None
        start_time = time.time()
        max_wait_seconds = 300  # 最多等待 5 分钟
        user_id = user.id  # 保存 user_id
        
        try:
            # 创建独立的数据库 session（关键修复）
            async with AsyncSessionLocal() as db:
                # 先检查任务是否存在
                job = (
                    await db.execute(
                        select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user_id)
                    )
                ).scalar_one_or_none()
                
                if not job:
                    yield f"event: error\ndata: {json.dumps({'message': '任务不存在'})}\n\n"
                    return
                
                # 推送初始状态
                last_status = job.status
                status_data = {
                    "job_id": job.uuid,
                    "status": job.status.value,
                    "timestamp": time.time()
                }
                yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
            
            # 如果任务已完成，直接返回
            if last_status in [JobStatus.succeeded, JobStatus.failed]:
                async with AsyncSessionLocal() as db:
                    job = (await db.execute(select(TTSJob).where(TTSJob.uuid == job_uuid))).scalar_one()
                    tts_data = _tts_out(job)
                    complete_data = {
                        "job_id": job.uuid,
                        "status": job.status.value,
                        "data": tts_data.model_dump()
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                return
            
            # 循环检查状态
            while True:
                # 检查超时
                if time.time() - start_time > max_wait_seconds:
                    yield f"event: timeout\ndata: {json.dumps({'message': '任务处理超时', 'elapsed_seconds': max_wait_seconds})}\n\n"
                    break
                
                # 等待 1 秒后再次查询
                await asyncio.sleep(1)
                
                # 每次查询使用新的 session
                async with AsyncSessionLocal() as db:
                    # 查询任务状态
                    job = (
                        await db.execute(
                            select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user_id)
                        )
                    ).scalar_one_or_none()
                    
                    if not job:
                        yield f"event: error\ndata: {json.dumps({'message': '任务已被删除'})}\n\n"
                        break
                    
                    # 状态变化时推送
                    if job.status != last_status:
                        status_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "timestamp": time.time()
                        }
                        yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                        last_status = job.status
                    
                    # 任务完成时推送完整信息
                    if job.status in [JobStatus.succeeded, JobStatus.failed]:
                        tts_data = _tts_out(job)
                        complete_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "data": tts_data.model_dump()
                        }
                        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                        break
                
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()  # 打印到服务器日志
            yield f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@openapi_router.get("/tts/jobs/{job_uuid}/events")
async def openapi_stream_tts_events(
    job_uuid: str,
    principal: OpenAPIPrincipal = Depends(require_openapi_principal),
):
    """
    通过 SSE 流式推送 TTS 任务状态更新（OpenAPI）
    
    返回格式：
    - event: status - 状态变化事件
    - event: complete - 任务完成事件（成功或失败）
    - event: error - 错误事件
    - event: timeout - 超时事件
    """
    async def event_generator():
        from app.db import AsyncSessionLocal  # 导入 session 工厂
        
        last_status = None
        start_time = time.time()
        max_wait_seconds = 300  # 最多等待 5 分钟
        user_id = principal.user.id  # 保存 user_id
        
        try:
            # 创建独立的数据库 session（关键修复）
            async with AsyncSessionLocal() as db:
                # 先检查任务是否存在
                job = (
                    await db.execute(
                        select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user_id)
                    )
                ).scalar_one_or_none()
                
                if not job:
                    yield f"event: error\ndata: {json.dumps({'message': '任务不存在'})}\n\n"
                    return
                
                # 推送初始状态
                last_status = job.status
                status_data = {
                    "job_id": job.uuid,
                    "status": job.status.value,
                    "timestamp": time.time()
                }
                yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
            
            # 如果任务已完成，直接返回
            if last_status in [JobStatus.succeeded, JobStatus.failed]:
                async with AsyncSessionLocal() as db:
                    job = (await db.execute(select(TTSJob).where(TTSJob.uuid == job_uuid))).scalar_one()
                    tts_data = _tts_out(job)
                    complete_data = {
                        "job_id": job.uuid,
                        "status": job.status.value,
                        "data": tts_data.model_dump()
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                return
            
            # 循环检查状态
            while True:
                # 检查超时
                if time.time() - start_time > max_wait_seconds:
                    yield f"event: timeout\ndata: {json.dumps({'message': '任务处理超时', 'elapsed_seconds': max_wait_seconds})}\n\n"
                    break
                
                # 等待 1 秒后再次查询
                await asyncio.sleep(1)
                
                # 每次查询使用新的 session
                async with AsyncSessionLocal() as db:
                    # 查询任务状态
                    job = (
                        await db.execute(
                            select(TTSJob).where(TTSJob.uuid == job_uuid, TTSJob.user_id == user_id)
                        )
                    ).scalar_one_or_none()
                    
                    if not job:
                        yield f"event: error\ndata: {json.dumps({'message': '任务已被删除'})}\n\n"
                        break
                    
                    # 状态变化时推送
                    if job.status != last_status:
                        status_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "timestamp": time.time()
                        }
                        yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
                        last_status = job.status
                    
                    # 任务完成时推送完整信息
                    if job.status in [JobStatus.succeeded, JobStatus.failed]:
                        tts_data = _tts_out(job)
                        complete_data = {
                            "job_id": job.uuid,
                            "status": job.status.value,
                            "data": tts_data.model_dump()
                        }
                        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                        break
                
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()  # 打印到服务器日志
            yield f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
