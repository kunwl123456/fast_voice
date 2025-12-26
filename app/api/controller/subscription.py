"""订阅管理业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import SubscriptionError
from app.core.exceptions import BadRequestException
from app.api.services.billing import get_or_create_account
from app.core.models import CreditTransaction, TxType, User
from app.core.schemas import SubscriptionInfo, UpgradeSubscriptionOut, format_datetime
from app.core.constants import (
    PlanConfig,
    SUBSCRIPTION_PLANS,
    SubscriptionPlanType,
    SUBSCRIPTION_MIN_MONTHS,
    SUBSCRIPTION_MAX_MONTHS,
    SUBSCRIPTION_DAYS_PER_MONTH,
)


def has_api_access(plan: str) -> bool:
    """
    检查订阅计划是否有API访问权限

    Args:
        plan: 订阅计划代码

    Returns:
        bool: 是否有API访问权限
    """
    config = get_plan_config(plan)
    return config.api_access


def get_plan_config(plan: str) -> PlanConfig:
    """
    获取计划配置

    Args:
        plan: 订阅计划代码 (free/pro/enterprise)

    Returns:
        PlanConfig: 计划配置对象，如果计划不存在则返回免费版配置
    """
    return SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["free"])


async def get_user_subscription(user: User) -> SubscriptionInfo:
    """
    获取用户的订阅信息

    ### 参数
    - user: 用户对象

    ### 返回
    - 订阅信息对象
    """
    plan_config = get_plan_config(user.subscription_plan.value)

    # 判断订阅状态
    status = "active"
    if user.subscription_ends_at:
        if user.subscription_ends_at < datetime.now(ZoneInfo("Asia/Shanghai")):
            status = "expired"

    return SubscriptionInfo(
        plan=user.subscription_plan.value,
        plan_name=plan_config.name,
        status=status,
        ends_at=user.subscription_ends_at,
        features={
            "monthly_credits": plan_config.monthly_credits,
            "monthly_quota": plan_config.monthly_quota,
            "clone_limit": plan_config.clone_limit,
            "api_access": plan_config.api_access,
            "commercial_use": plan_config.commercial_use,
            "priority_support": plan_config.priority_support,
        },
    )


async def upgrade_user_subscription(
    db: AsyncSession, user: User, plan: str, months: int
) -> UpgradeSubscriptionOut:
    """
    升级用户的订阅计划

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - plan: 目标订阅计划（pro/enterprise）
    - months: 订阅月数

    ### 返回
    - 升级结果（包含计划、到期时间、赠送积分）
    """
    # 校验计划类型
    if plan not in SubscriptionPlanType.can_upgrade_plans():
        raise BadRequestException(
            error=SubscriptionError.INVALID_PLAN,
            data={"valid_plans": SubscriptionPlanType.can_upgrade_plans()},
        )

    # 校验订阅月数范围
    if not (SUBSCRIPTION_MIN_MONTHS <= months <= SUBSCRIPTION_MAX_MONTHS):
        raise BadRequestException(
            error=SubscriptionError.INVALID_DURATION,
            data={
                "months": months,
                "min_months": SUBSCRIPTION_MIN_MONTHS,
                "max_months": SUBSCRIPTION_MAX_MONTHS,
            },
        )

    # 计算订阅到期时间
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    ends_at = now + timedelta(days=SUBSCRIPTION_DAYS_PER_MONTH * months)

    # 更新用户订阅（直接赋值字符串，避免枚举转换的同步操作）
    user.subscription_plan = plan  # type: ignore
    user.subscription_ends_at = ends_at
    db.add(user)
    await db.flush()

    # 赠送对应的月度积分
    plan_config = get_plan_config(plan)
    acc = await get_or_create_account(db, user.id)
    credits_added = plan_config.monthly_credits * months
    acc.balance += credits_added
    db.add(acc)
    await db.flush()

    # 记录积分流水
    tx = CreditTransaction(
        account_id=acc.id,
        tx_type=TxType.subscription,
        amount=credits_added,
        ref_type="subscription",
        ref_id=f"{plan}_{months}m",
        note=f"订阅{plan_config.name}{months}个月赠送积分",
    )
    db.add(tx)

    return UpgradeSubscriptionOut(
        plan=plan,
        ends_at=format_datetime(ends_at),
        credits_added=credits_added,
    )
