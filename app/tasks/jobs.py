from __future__ import annotations

import os
import wave

from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.db_sync import SessionLocalSync
from app.models import CloneJob, JobStatus, TTSJob, Voice, format_timezone
from app.services.billing_sync import refund
from app.services.storage import job_dir
from app.tasks.celery_app import celery_app

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


@celery_app.task(name="app.tasks.jobs.run_tts_job")
def run_tts_job(job_id: int) -> None:
    with SessionLocalSync() as db:
        job = db.execute(select(TTSJob).where(TTSJob.id == job_id)).scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.running
        job.updated_at = format_timezone()
        db.commit()

    try:
        out_dir = job_dir("tts", user_id=job.user_id, job_id=job_id)
        out_path = os.path.join(out_dir, "output.wav")
        _write_dummy_wav(out_path, seconds=1.0)
        with SessionLocalSync() as db:
            job = db.execute(select(TTSJob).where(TTSJob.id == job_id)).scalar_one()
            job.status = JobStatus.succeeded
            job.output_audio_path = out_path
            job.updated_at = format_timezone()
            db.commit()
    except Exception as e:
        logger.exception("tts job failed: %s", e)
        with SessionLocalSync() as db:
            job = db.execute(select(TTSJob).where(TTSJob.id == job_id)).scalar_one_or_none()
            if not job:
                return
            job.status = JobStatus.failed
            job.error = "tts_failed"
            job.updated_at = format_timezone()
            refund(db=db, user_id=job.user_id, amount=job.cost_credits, ref_type="tts", ref_id=str(job.id))
            db.commit()


@celery_app.task(name="app.tasks.jobs.run_clone_job")
def run_clone_job(job_id: int) -> None:
    with SessionLocalSync() as db:
        job = db.execute(select(CloneJob).where(CloneJob.id == job_id)).scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.running
        job.updated_at = format_timezone()
        db.commit()

    try:
        # V1：先不做真实训练，直接创建 Voice，并生成预览音频
        with SessionLocalSync() as db:
            job = db.execute(select(CloneJob).where(CloneJob.id == job_id)).scalar_one()
            v = Voice(
                owner_user_id=job.user_id,
                name=job.voice_name,
                description="",
                is_public=job.is_public,
                preview_audio_path="",
            )
            db.add(v)
            db.flush()
            out_dir = job_dir("clone", user_id=job.user_id, job_id=job_id)
            preview_path = os.path.join(out_dir, "preview.wav")
            _write_dummy_wav(preview_path, seconds=1.0)
            v.preview_audio_path = preview_path
            job.result_voice_id = v.id
            job.status = JobStatus.succeeded
            job.updated_at = format_timezone()
            db.commit()
    except Exception as e:
        logger.exception("clone job failed: %s", e)
        with SessionLocalSync() as db:
            job = db.execute(select(CloneJob).where(CloneJob.id == job_id)).scalar_one_or_none()
            if not job:
                return
            job.status = JobStatus.failed
            job.error = "clone_failed"
            job.updated_at = format_timezone()
            db.commit()



