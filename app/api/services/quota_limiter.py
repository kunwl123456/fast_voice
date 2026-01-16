"""
月度配额限流服务
功能：基于Redis实现高性能的月度API请求配额限制
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from redis import asyncio as aioredis
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.config import settings
from app.core.error_codes import SubscriptionError
from app.core.exceptions import BadRequestException
from app.api.services.plan_config import get_plan_config_by_id


class QuotaLimiter:
    """月度配额限流器（基于Redis）"""

    _redis_client: aioredis.Redis | None = None

    @classmethod
    async def get_client(cls) -> aioredis.Redis | None:
        """获取Redis客户端（单例）"""
        if cls._redis_client is None:
            redis_url = settings.redis_url
            if not redis_url:
                logger.warning("Redis未配置，配额限制功能禁用")
                return None

            try:
                cls._redis_client = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                await cls._redis_client.ping()
                logger.info("配额限流器Redis连接成功")
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                cls._redis_client = None

        return cls._redis_client

    @classmethod
    def _get_quota_key(cls, user_id: int, month: str) -> str:
        """
        生成配额计数器的Redis键

        格式: quota:{user_id}:{YYYYMM}
        例如: quota:123:202412
        """
        return f"quota:{user_id}:{month}"

    @classmethod
    def _get_current_month(cls) -> str:
        """获取当前月份标识 (YYYYMM)"""
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m")

    @classmethod
    async def check_and_increment(
        cls, user: User, db: AsyncSession
    ) -> tuple[bool, int, int]:
        """
        检查并递增用户的月度配额使用量

        Args:
            user: 用户对象

        Returns:
            tuple[bool, int, int]: (是否允许, 当前使用量, 配额上限)

        Raises:
            BadRequestException: 超过配额限制时抛出异常
        """
        # 获取用户的配额限制
        plan_config = await get_plan_config_by_id(db, user.subscription_plan_id)
        if not plan_config:
            # 配置缺失，默认拒绝
            raise BadRequestException(
                message="订阅计划配置错误",
                error=SubscriptionError.INVALID_PLAN,
            )

        quota_limit = plan_config.monthly_quota

        # 如果Redis不可用，只记录警告，允许通过（降级方案）
        client = await cls.get_client()
        if client is None:
            logger.warning(f"Redis不可用，配额检查降级通过 (user={user.email})")
            return True, 0, quota_limit

        # 生成本月的配额键
        month = cls._get_current_month()
        key = cls._get_quota_key(user.id, month)

        try:
            # 原子操作：获取当前值并递增
            current_usage = await client.incr(key)

            # 设置过期时间（60天，确保不会积累过多键）
            if current_usage == 1:  # 首次创建时设置TTL
                await client.expire(key, 60 * 24 * 3600)  # 60天

            # 检查是否超过限制
            if current_usage > quota_limit:
                # 已超过配额，拒绝请求
                logger.warning(
                    f"用户 {user.email} 超过月度配额: " f"{current_usage}/{quota_limit}"
                )
                raise BadRequestException(
                    message=f"已超过月度请求配额（{quota_limit}次/月）",
                    error=SubscriptionError.EXCEED_QUOTA,
                    data={
                        "current_usage": current_usage - 1,  # 减去本次
                        "quota_limit": quota_limit,
                        "month": month,
                    },
                )

            return True, current_usage, quota_limit

        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"配额检查失败: {e}")
            # Redis操作失败，降级允许通过
            return True, 0, quota_limit

    @classmethod
    async def get_usage(cls, user: User, db: AsyncSession) -> tuple[int, int]:
        """
        获取用户当月的配额使用情况（不递增）

        Args:
            user: 用户对象
            db: 数据库会话

        Returns:
            tuple[int, int]: (当前使用量, 配额上限)
        """
        plan_config = await get_plan_config_by_id(db, user.subscription_plan_id)
        if not plan_config:
            return 0, 0

        quota_limit = plan_config.monthly_quota

        client = await cls.get_client()
        if client is None:
            return 0, quota_limit

        month = cls._get_current_month()
        key = cls._get_quota_key(user.id, month)

        try:
            usage = await client.get(key)
            current_usage = int(usage) if usage else 0
            return current_usage, quota_limit
        except Exception as e:
            logger.error(f"获取配额使用量失败: {e}")
            return 0, quota_limit

    @classmethod
    async def reset_user_quota(cls, user_id: int, month: str | None = None) -> bool:
        """
        重置用户的月度配额（管理员功能）

        Args:
            user_id: 用户ID
            month: 月份标识(YYYYMM)，为None时重置当前月份

        Returns:
            bool: 是否重置成功
        """
        client = await cls.get_client()
        if client is None:
            return False

        if month is None:
            month = cls._get_current_month()

        key = cls._get_quota_key(user_id, month)

        try:
            await client.delete(key)
            logger.info(f"已重置用户 {user_id} 的配额计数器 ({month})")
            return True
        except Exception as e:
            logger.error(f"重置配额失败: {e}")
            return False
