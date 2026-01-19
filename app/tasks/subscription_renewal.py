import asyncio

from app.core.db import AsyncSessionLocal
from app.tasks.celery_app import celery_app
from app.api.services.subscription_renewal import (
    renew_monthly_credits_batch,
    downgrade_expired_users,
)


@celery_app.task
def renew_monthly_credits_task():
    """月度积分续赠定时任务（每日执行，检查是否满足30天周期）"""

    async def run():
        db = AsyncSessionLocal()
        try:
            stats = await renew_monthly_credits_batch(db)
            return stats
        finally:
            await db.close()

    return asyncio.run(run())


@celery_app.task
def check_expired_subscriptions_task():
    """过期订阅检查定时任务（每日凌晨4点执行）"""

    async def run():
        db = AsyncSessionLocal()
        try:
            stats = await downgrade_expired_users(db)
            return stats
        finally:
            await db.close()

    return asyncio.run(run())
