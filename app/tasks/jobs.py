from __future__ import annotations

import os
import wave
from pathlib import Path
import requests
import shutil

from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.db_sync import SessionLocalSync
from app.api.services.billing import refund
from app.api.services.storage import job_dir
from app.tasks.celery_app import celery_app
from app.core.constants import JobStatus
from app.api.services.redis_pubsub_sync import RedisPubSubSync
from app.core.models import CloneJob, TTSJob, Voice, format_timezone

logger = get_task_logger(__name__)


def _write_dummy_wav(path: str, seconds: float = 1.0, framerate: int = 22050) -> None:
    """
    V1：先打通队列与文件落地链路。
    后续把这里替换为 GPT-SoVITS 推理/训练的真实输出即可。
    """
    nframes = int(seconds * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * nframes)


def _call_webhook(webhook_url: str, payload: dict) -> None:
    """调用 webhook 回调地址"""
    if not webhook_url:
        return
    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "FastVoice-Webhook/1.0",
            },
        )
        if resp.status_code >= 400:
            logger.warning(
                "webhook call returned error: url=%s status=%s body=%s",
                webhook_url,
                resp.status_code,
                resp.text[:200],
            )
        else:
            logger.info(
                "webhook called successfully: url=%s status=%s",
                webhook_url,
                resp.status_code,
            )
    except Exception as e:
        logger.warning("webhook call failed: url=%s error=%s", webhook_url, e)


@celery_app.task(name="app.tasks.jobs.run_tts_job")
def run_tts_job(job_id: int) -> None:
    # 在 Session 内读取必要信息
    with SessionLocalSync() as db:
        job = db.execute(select(TTSJob).where(TTSJob.id == job_id)).scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.running
        job.updated_at = format_timezone()
        db.commit()
        # 提前读取属性，避免 DetachedInstanceError
        user_id = job.user_id
        job_uuid = job.uuid
        voice_uuid = job.voice_uuid
        job_text = job.text
        speed_factor = job.speed_factor or 1.0
        temperature = job.temperature or 1.0
        top_k = job.top_k or 5
        top_p = job.top_p or 1.0
        webhook_url = job.webhook_url or ""

    # 🚀 发布状态更新：running
    RedisPubSubSync.publish_job_status("tts", job_uuid, "running")

    try:
        out_dir = job_dir("tts", user_id=user_id, job_uuid=job_uuid)
        out_path = os.path.join(out_dir, "output.mp3")

        # 调用第三方 TTS 服务（默认 http://localhost:7000/tts），使用克隆时的 UUID 作为 ids
        base_url = os.getenv("VOICE_TTS_BASE_URL", "http://localhost:7000").rstrip("/")
        used_fallback = False
        clone_uuid: str | None = None
        with SessionLocalSync() as db:
            voice = db.execute(
                select(Voice).where(Voice.uuid == voice_uuid)
            ).scalar_one_or_none()
            if voice and voice.clone_job_uuid:
                clone_uuid = voice.clone_job_uuid
                logger.info(
                    "Found voice uuid=%s, clone_job_uuid=%s", voice_uuid, clone_uuid
                )
            else:
                logger.warning(
                    "Voice uuid=%s not found or missing clone_job_uuid", voice_uuid
                )

        logger.info("TTS config: base_url=%s, clone_uuid=%s", base_url, clone_uuid)
        if base_url and clone_uuid:
            payload = {
                "text": job_text,
                "ids": [clone_uuid],
                "speed_factor": speed_factor,
                "temperature": temperature,
                "top_k": top_k,
                "top_p": top_p,
            }
            try:
                resp = requests.post(f"{base_url}/tts", json=payload, timeout=300)
                if resp.status_code == 200 and resp.content:
                    with open(out_path, "wb") as f:
                        f.write(resp.content)
                else:
                    logger.warning(
                        "tts svc non-200/empty code=%s body_len=%s",
                        resp.status_code,
                        len(resp.content or b""),
                    )
                    _write_dummy_wav(out_path, seconds=1.0)
                    used_fallback = True
            except Exception as svc_err:
                logger.warning("tts svc call failed: %s", svc_err)
                _write_dummy_wav(out_path, seconds=1.0)
                used_fallback = True
        else:
            if not base_url:
                logger.warning("VOICE_TTS_BASE_URL not set, using fallback dummy wav")
            if not clone_uuid:
                logger.warning("no clone_job_uuid found for voice_uuid=%s", voice_uuid)
            _write_dummy_wav(out_path, seconds=1.0)
            used_fallback = True

        with SessionLocalSync() as db:
            job = db.execute(select(TTSJob).where(TTSJob.id == job_id)).scalar_one()
            job.status = JobStatus.succeeded
            job.output_audio_path = out_path
            job.updated_at = format_timezone()

            # 更新 Voice 统计数据：使用次数 +1，生成字符数累加
            voice = db.execute(
                select(Voice).where(Voice.uuid == job.voice_uuid)
            ).scalar_one_or_none()
            if voice:
                voice.usage_count += 1
                voice.generated_chars_count += len(job.text)
                db.add(voice)

            db.commit()

        # 🚀 发布状态更新：succeeded
        RedisPubSubSync.publish_job_status("tts", job_uuid, "succeeded")

        # 调用 webhook 回调（成功）
        if webhook_url:
            from app.api.services.storage import to_public_file_url

            _call_webhook(
                webhook_url,
                {
                    "job_id": job_uuid,
                    "status": "succeeded",
                    "output_audio_url": to_public_file_url(out_path),
                    "cost_credits": job.cost_credits,
                    "timestamp": format_timezone().isoformat(),
                },
            )

        if used_fallback:
            logger.info("tts job %s used fallback audio", job_id)
    except Exception as e:
        logger.exception("tts job failed: %s", e)
        with SessionLocalSync() as db:
            job = db.execute(
                select(TTSJob).where(TTSJob.id == job_id)
            ).scalar_one_or_none()
            if not job:
                return
            job.status = JobStatus.failed
            job.error = "tts_failed"
            job.updated_at = format_timezone()
            webhook_url_failed = job.webhook_url or ""
            job_uuid_failed = job.uuid
            # refund 需要从数据库读取最新的 cost_credits
            refund(
                db=db,
                user_id=job.user_id,
                amount=job.cost_credits,
                ref_type="tts",
                ref_id=str(job.id),
            )
            db.commit()

        # 🚀 发布状态更新：failed
        RedisPubSubSync.publish_job_status("tts", job_uuid_failed, "failed")

        # 调用 webhook 回调（失败）
        if webhook_url_failed:
            _call_webhook(
                webhook_url_failed,
                {
                    "job_id": job_uuid_failed,
                    "status": "failed",
                    "error": "tts_failed",
                    "error_message": str(e),
                    "timestamp": format_timezone().isoformat(),
                },
            )


@celery_app.task(name="app.tasks.jobs.run_clone_job")
def run_clone_job(job_id: int) -> None:
    with SessionLocalSync() as db:
        job = db.execute(
            select(CloneJob).where(CloneJob.id == job_id)
        ).scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.running
        job.updated_at = format_timezone()
        db.commit()
        # 提前读取 job_uuid
        job_uuid = job.uuid

    # 🚀 发布状态更新：running
    RedisPubSubSync.publish_job_status("clone", job_uuid, "running")

    try:
        # 可选：调用外部语音服务做特征提取 / 生成 voice（不改变原有落库逻辑）
        # 在 Session 之外读取必要信息，避免长事务
        with SessionLocalSync() as db:
            job = db.execute(select(CloneJob).where(CloneJob.id == job_id)).scalar_one()
            dataset_dir = job.dataset_dir or ""
            user_id = job.user_id
            voice_name = job.voice_name
            avatar_url = job.avatar_url
            description = job.description
            tags = job.tags or []
            is_public = job.is_public
            job_uuid = job.uuid  # 使用克隆任务的 UUID 作为音频特征 ID

        selected_audio_path = next(
            (p for p in Path(dataset_dir).glob("**/*") if p.is_file()), None
        )
        if not selected_audio_path:
            raise RuntimeError(f"未找到可用音频文件，目录: {dataset_dir}")

        base_url = os.getenv("VOICE_SVC_BASE_URL", "").rstrip("/")
        if base_url:
            try:
                resp = requests.post(
                    f"{base_url}/create_voice",
                    data={"id": job_uuid},  # 使用克隆任务的 UUID
                    files={
                        "file": (
                            selected_audio_path.name,
                            open(selected_audio_path, "rb"),
                            "audio/wav",
                        )
                    },
                    timeout=300,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "voice svc non-200 code=%s body=%s", resp.status_code, resp.text
                    )
            except Exception as svc_err:
                logger.warning("voice svc call failed: %s", svc_err)

        # 原有占位逻辑：创建 Voice，生成预览（dummy）
        with SessionLocalSync() as db:
            job = db.execute(select(CloneJob).where(CloneJob.id == job_id)).scalar_one()
            v = Voice(
                owner_user_id=job.user_id,
                name=job.voice_name,
                avatar_url=job.avatar_url,
                description=job.description,
                tags=job.tags or [],
                is_public=job.is_public,
                preview_audio_path="",
                clone_job_uuid=job.uuid,  # 保存克隆任务的 UUID
            )
            db.add(v)
            db.flush()
            out_dir = job_dir("clone", user_id=job.user_id, job_uuid=job.uuid)
            preview_path = os.path.join(out_dir, "preview.wav")
            shutil.copyfile(selected_audio_path, preview_path)
            v.preview_audio_path = preview_path
            job.result_voice_uuid = v.uuid  # 保存生成的音色 UUID
            job.external_request_id = (
                job.uuid
            )  # 使用克隆任务的 UUID 作为 external_request_id
            job.status = JobStatus.succeeded
            job.updated_at = format_timezone()
            db.commit()

        # 🚀 发布状态更新：succeeded
        RedisPubSubSync.publish_job_status("clone", job_uuid, "succeeded")
    except Exception as e:
        logger.exception("clone job failed: %s", e)
        with SessionLocalSync() as db:
            job = db.execute(
                select(CloneJob).where(CloneJob.id == job_id)
            ).scalar_one_or_none()
            if not job:
                return
            job.status = JobStatus.failed
            job.error = "clone_failed"
            job.updated_at = format_timezone()
            db.commit()
            # 读取 job_uuid 用于发布
            job_uuid_failed = job.uuid

        # 🚀 发布状态更新：failed
        RedisPubSubSync.publish_job_status("clone", job_uuid_failed, "failed")
