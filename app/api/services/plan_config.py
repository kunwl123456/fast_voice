"""
订阅计划配置服务
从数据库读取订阅计划配置，提供缓存机制
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import SubscriptionPlanConfig


async def get_plan_config_by_id(
    db: AsyncSession, pk: int
) -> SubscriptionPlanConfig | None:
    """
    获取单个订阅计划配置
    """
    result = await db.execute(
        select(SubscriptionPlanConfig).where(
            SubscriptionPlanConfig.id == pk,
            SubscriptionPlanConfig.is_active.is_(True),
        )
    )
    return result.scalars().first()


async def query_plan_config(
    db: AsyncSession, plan_code: str
) -> SubscriptionPlanConfig | None:
    """
    查询订阅计划配置
    """
    result = await db.execute(
        select(SubscriptionPlanConfig).where(
            SubscriptionPlanConfig.plan_code == plan_code,
            SubscriptionPlanConfig.is_active.is_(True),
        )
    )
    return result.scalars().first()
