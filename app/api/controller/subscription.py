"""订阅管理业务逻辑"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import CreateOrderIn
from app.core.error_codes import SubscriptionError
from app.api.controller.orders import create_order
from app.core.exceptions import BadRequestException
from app.api.services.quota_limiter import QuotaLimiter
from app.api.services.billing import get_or_create_account
from app.api.services.clone_limit_checker import get_clone_usage
from app.api.services.plan_config import query_plan_config, get_plan_config_by_id
from app.core.models import (
    User,
    CreditAccount,
    CreditTransaction,
    SubscriptionPlanConfig,
)
from app.core.schemas import (
    CreateOrderOut,
    SubscriptionInfo,
    PlanConfigOut,
)
from app.core.constants import (
    TxType,
    Currency,
    OrderType,
    PaymentProvider,
    CAN_UPGRADE_PLANS,
    SUBSCRIPTION_MIN_MONTHS,
    SUBSCRIPTION_MAX_MONTHS,
)


async def get_all_plan_configs(db: AsyncSession) -> list[PlanConfigOut]:
    """
    获取所有订阅计划的配置信息

    Args:
        db: 数据库会话

    Returns:
        list[PlanConfigOut]: 所有订阅计划配置列表
    """
    result = await db.execute(
        select(SubscriptionPlanConfig).where(SubscriptionPlanConfig.is_active == True)
    )
    plans = result.scalars().all()

    # 将 SQLAlchemy 模型转换为 Pydantic 模型
    return [
        PlanConfigOut(
            id=plan.id,
            plan=plan.plan_code,
            name=plan.name,
            monthly_credits=plan.monthly_credits,
            monthly_quota=plan.monthly_quota,
            clone_limit=plan.clone_limit,
            api_access=plan.api_access,
            commercial_use=plan.commercial_use,
            priority_support=plan.priority_support,
            monthly_price=plan.monthly_price,
            currency=plan.currency,
        )
        for plan in plans
    ]


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
    plan_config = await get_plan_config_by_id(db, user.subscription_plan_id)

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
    quota_usage, quota_total = await QuotaLimiter.get_usage(user, db)
    clone_usage, clone_total = await get_clone_usage(db, user)

    # 计算可用量
    quota_available = quota_total - quota_usage
    clone_available = clone_total - clone_usage

    return SubscriptionInfo(
        plan=str(plan_config.plan_code),
        plan_name=str(plan_config.name),
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
    db: AsyncSession,
    user: User,
    plan: str,
    months: int,
    pay_type: str,
) -> CreateOrderOut:
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
    if plan not in CAN_UPGRADE_PLANS:
        raise BadRequestException(
            error=SubscriptionError.INVALID_PLAN,
            data={"valid_plans": CAN_UPGRADE_PLANS},
        )

    # 策略限制：Enterprise 仅支持后台开通
    if plan == "enterprise":
        raise BadRequestException(
            message="企业版订阅请联系商务或管理员开通",
            error=SubscriptionError.INVALID_PLAN,
        )

    # 获取当前用户的订阅计划配置
    current_plan_config = await get_plan_config_by_id(db, user.subscription_plan_id)
    current_plan_code = current_plan_config.plan_code if current_plan_config else "free"

    # 策略限制：Free -> Pro 升级限制
    if current_plan_code == "free" and plan == "pro":
        if months != 1:
            raise BadRequestException(
                message="首次升级专业版仅支持订阅 1 个月",
                error=SubscriptionError.INVALID_DURATION,
                data={"allowed_months": 1},
            )

    # 策略限制：不允许自助降级（如 Pro -> Free 或 Enterprise -> Pro）
    # 注意：这里简单通过 plan_code 比较可能不准确，理想情况应比较 price 或 level
    # 假设 level: free < pro < enterprise
    plan_levels = {"free": 0, "pro": 1, "enterprise": 2}
    current_level = plan_levels.get(current_plan_code, 0)
    target_level = plan_levels.get(plan, 0)

    if target_level < current_level:
        raise BadRequestException(
            message="不支持自助降级订阅，请等待当前订阅过期",
            error=SubscriptionError.INVALID_PLAN,
        )

    all_pay_types = list(PaymentProvider.__members__.keys())
    if pay_type not in all_pay_types:
        raise BadRequestException(
            error=SubscriptionError.INVALID_PAY_TYPE,
            data={"valid_pay_types": all_pay_types},
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

    # 获取订阅计划配置
    plan_config = await query_plan_config(db, plan)
    if not plan_config:
        raise BadRequestException(
            error=SubscriptionError.INVALID_PLAN,
            message="订阅计划配置不存在",
        )

    extra_metadata = {
        "quantity": months,
        "currency": plan_config.currency,
        "product_name": plan_config.name,
        "plan_code": plan_config.plan_code,
        "unit_price": plan_config.monthly_price,
        "total_price": plan_config.monthly_price * months,
    }
    return await create_order(
        db,
        user,
        CreateOrderIn(
            order_type=OrderType.subscription.value,
            product_id=plan_config.id,
            product_name=plan_config.name,
            quantity=months,
            payment_method=PaymentProvider(pay_type),
            currency=Currency(plan_config.currency),
            unit_price=plan_config.monthly_price,
            extra_metadata=extra_metadata,
        ),
    )
