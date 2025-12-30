"""
订阅计划自动续赠服务
功能：每月自动为付费用户续赠积分
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.models import User, CreditTransaction, TxType
from app.core.constants import SUBSCRIPTION_PLANS, SubscriptionPlanType
from app.api.services.billing import get_or_create_account


async def renew_monthly_credits_for_user(db: AsyncSession, user: User) -> int:
    """
    为单个用户续赠月度积分

    Args:
        db: 数据库会话
        user: 用户对象

    Returns:
        int: 本次续赠的积分数量（0表示无需续赠）
    """
    # 免费用户不续赠（注册时已给初始积分）
    if user.subscription_plan == SubscriptionPlanType.free:
        return 0

    # 检查订阅是否有效
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if user.subscription_ends_at and user.subscription_ends_at < now:
        logger.info(f"用户 {user.email} 订阅已过期，跳过续赠")
        return 0

    # 获取计划配置
    plan_config = SUBSCRIPTION_PLANS.get(user.subscription_plan.value)
    if not plan_config:
        logger.warning(f"未找到用户 {user.email} 的计划配置")
        return 0

    # 获取积分账户
    acc = await get_or_create_account(db, user.id)
    credits_to_add = plan_config.monthly_credits

    # 增加积分
    acc.balance += credits_to_add
    db.add(acc)

    # 记录流水
    tx = CreditTransaction(
        account_id=acc.id,
        tx_type=TxType.subscription,
        amount=credits_to_add,
        ref_type="monthly_renewal",
        ref_id=f"{user.subscription_plan.value}_{now.strftime('%Y%m')}",
        note=f"月度自动续赠积分（{plan_config.name}）",
    )
    db.add(tx)

    logger.info(
        f"为用户 {user.email} 续赠 {credits_to_add} 积分" f"（{plan_config.name}）"
    )

    return credits_to_add


async def renew_monthly_credits_batch(db: AsyncSession) -> dict:
    """
    批量为所有付费用户续赠月度积分

    定时任务：每月1号凌晨执行

    Returns:
        dict: 续赠统计信息
    """
    logger.info("开始执行月度积分续赠任务")

    # 查询所有付费且订阅未过期的用户
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    users = (
        (
            await db.execute(
                select(User).where(
                    User.subscription_plan != SubscriptionPlanType.free,
                    User.subscription_ends_at > now,
                )
            )
        )
        .scalars()
        .all()
    )

    stats = {
        "total_users": len(users),
        "success_count": 0,
        "failed_count": 0,
        "total_credits": 0,
    }

    for user in users:
        try:
            credits = await renew_monthly_credits_for_user(db, user)
            if credits > 0:
                stats["success_count"] += 1
                stats["total_credits"] += credits
        except Exception as e:
            stats["failed_count"] += 1
            logger.error(f"为用户 {user.email} 续赠积分失败: {e}")

    await db.commit()

    logger.info(
        f"月度积分续赠任务完成: "
        f"成功 {stats['success_count']}/{stats['total_users']} 用户, "
        f"总计 {stats['total_credits']} 积分"
    )

    return stats
