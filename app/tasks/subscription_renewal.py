from app.tasks.celery_app import celery_app


@celery_app.task
def renew_monthly_credits_task():
    """月度积分续赠定时任务（每月1号凌晨3点执行）"""
    import asyncio
    from app.core.db import AsyncSessionLocal
    from app.api.services.subscription_renewal import renew_monthly_credits_batch

    async def run():
        db = AsyncSessionLocal()
        try:
            stats = await renew_monthly_credits_batch(db)
            return stats
        finally:
            await db.close()

    return asyncio.run(run())
