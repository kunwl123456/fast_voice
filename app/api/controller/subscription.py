"""订阅管理业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.error_codes import SubscriptionError
from app.core.exceptions import BadRequestException
from app.api.services.quota_limiter import QuotaLimiter
from app.api.services.billing import get_or_create_account
from app.api.services.clone_limit_checker import get_clone_usage
from app.core.models import CreditAccount, CreditTransaction, TxType, User
from app.core.schemas import (
    SubscriptionInfo,
    UpgradeSubscriptionOut,
    format_datetime,
    PlanConfigOut,
)
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


def get_all_plan_configs() -> list[PlanConfigOut]:
    """
    获取所有订阅计划的配置信息

    Returns:
        list[PlanConfigOut]: 所有订阅计划配置列表
    """
    result = []
    for plan_code, config in SUBSCRIPTION_PLANS.items():
        result.append(
            PlanConfigOut(
                plan=plan_code,
                name=config.name,
                monthly_credits=config.monthly_credits,
                monthly_quota=config.monthly_quota,
                clone_limit=config.clone_limit,
                api_access=config.api_access,
                commercial_use=config.commercial_use,
                priority_support=config.priority_support,
            )
        )
    return result


async def get_monthly_credits_used(db: AsyncSession, user_id: int) -> int:
    """
    获取当月已使用的积分数量（消费类型的交易）

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        int: 当月已使用的积分数（绝对值）
    """
    # 获取当月第一天
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 查询当月的消费记录（tx_type 为 consume 的负数交易）
    result = await db.execute(
        select(func.sum(CreditTransaction.amount))
        .join(CreditAccount, CreditTransaction.account_id == CreditAccount.id)
        .where(
            CreditAccount.user_id == user_id,
            CreditTransaction.tx_type == TxType.consume,
            CreditTransaction.created_at >= month_start,
        )
    )

    total = result.scalar() or 0
    # 消费记录是负数，返回绝对值
    return abs(total)


async def get_user_subscription(user: User, db: AsyncSession) -> SubscriptionInfo:
    """
    获取用户的订阅信息

    ### 参数
    - user: 用户对象
    - db: 数据库会话

    ### 返回
    - 订阅信息对象
    """
    plan_config = get_plan_config(user.subscription_plan.value)

    # 判断订阅状态
    status = "active"
    if user.subscription_ends_at:
        if user.subscription_ends_at < datetime.now(ZoneInfo("Asia/Shanghai")):
            status = "expired"

    # 获取用户积分账户余额
    acc = await get_or_create_account(db, user.id)
    credits_balance = acc.balance  # 账户总余额（可能包含多月积分）

    # 获取当月已使用的积分
    credits_used_this_month = await get_monthly_credits_used(db, user.id)

    # 获取配额和克隆使用情况
    quota_usage, quota_total = await QuotaLimiter.get_usage(user)
    clone_usage, clone_total = await get_clone_usage(db, user)

    # 计算可用量
    quota_available = quota_total - quota_usage
    clone_available = clone_total - clone_usage

    return SubscriptionInfo(
        plan=user.subscription_plan.value,
        plan_name=plan_config.name,
        status=status,
        ends_at=user.subscription_ends_at,
        features={
            # 积分相关
            "credits_monthly_quota": plan_config.monthly_credits,  # 每月配额（单月额度）
            "credits_balance": credits_balance,  # 账户余额（可跨月累积）
            "credits_used_this_month": credits_used_this_month,  # 本月已使用量
            # 克隆相关
            "clone_total": clone_total,  # 克隆总可用量
            "clone_used": clone_usage,  # 克隆已使用量
            "clone_available": clone_available,  # 克隆可用量
            # 配额相关
            "quota_total": quota_total,  # 配额总可用量
            "quota_used": quota_usage,  # 配额已使用量
            "quota_available": quota_available,  # 配额可用量
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
