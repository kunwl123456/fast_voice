"""
克隆位限制检查服务
功能：检查用户是否超过订阅计划的克隆位限制
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.models import User, Voice
from app.core.constants import SUBSCRIPTION_PLANS
from app.core.error_codes import CloneError
from app.core.exceptions import BadRequestException


async def check_clone_limit(db: AsyncSession, user: User) -> tuple[bool, int, int]:
    """
    检查用户是否可以创建新的克隆音色

    Args:
        db: 数据库会话
        user: 用户对象

    Returns:
        tuple[bool, int, int]: (是否允许创建, 当前克隆数, 克隆上限)

    Raises:
        BadRequestException: 超过克隆位限制时抛出异常
    """
    # 获取用户的克隆位限制
    plan_config = SUBSCRIPTION_PLANS.get(user.subscription_plan.value)
    if not plan_config:
        logger.error(f"未找到用户 {user.email} 的计划配置")
        raise BadRequestException(
            message="订阅计划配置错误",
            error=CloneError.INVALID_AUDIO_FORMAT,
        )

    clone_limit = plan_config.clone_limit

    # -1 表示无限制（企业版）
    if clone_limit == -1:
        return True, 0, -1

    # 查询用户当前克隆音色数量
    current_count = (
        await db.execute(
            select(func.count(Voice.id)).where(Voice.owner_user_id == user.id)
        )
    ).scalar() or 0

    # 检查是否超过限制
    if current_count >= clone_limit:
        logger.warning(
            f"用户 {user.email} 超过克隆位限制: {current_count}/{clone_limit}"
        )
        raise BadRequestException(
            message=f"已达到克隆位上限（{clone_limit}个），请升级订阅计划或删除旧克隆",
            error=CloneError.CLONE_LIMIT_EXCEEDED,
            data={
                "current_count": current_count,
                "clone_limit": clone_limit,
                "subscription_plan": user.subscription_plan.value,
            },
        )

    logger.info(f"用户 {user.email} 克隆位检查通过: {current_count}/{clone_limit}")

    return True, current_count, clone_limit


async def get_clone_usage(db: AsyncSession, user: User) -> tuple[int, int]:
    """
    获取用户的克隆位使用情况（不做限制检查）

    Args:
        db: 数据库会话
        user: 用户对象

    Returns:
        tuple[int, int]: (当前克隆数, 克隆上限)
    """
    plan_config = SUBSCRIPTION_PLANS.get(user.subscription_plan.value)
    if not plan_config:
        return 0, 0

    clone_limit = plan_config.clone_limit

    current_count = (
        await db.execute(
            select(func.count(Voice.id)).where(Voice.owner_user_id == user.id)
        )
    ).scalar() or 0

    return current_count, clone_limit
