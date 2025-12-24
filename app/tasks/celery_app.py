from __future__ import annotations

from celery import Celery

from app.core.config import settings


def _fallback_redis(url: str | None, default: str) -> str:
    return url or default


celery_app = Celery(
    "fast_voice",
    broker=_fallback_redis(settings.celery_broker_url, "redis://localhost:6379/1"),
    backend=_fallback_redis(settings.celery_result_backend, "redis://localhost:6379/2"),
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.jobs.run_tts_job": {"queue": "tts"},
        "app.tasks.jobs.run_clone_job": {"queue": "clone"},
    },
    imports=("app.tasks.jobs",),  # 确保 worker 注册任务
)

# 防止未注册任务：显式导入/发现 app.tasks 下的任务
celery_app.autodiscover_tasks(["app.tasks"])
