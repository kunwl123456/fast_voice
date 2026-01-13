"""订阅管理业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.common import tz_now
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
    Order,
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
    SUBSCRIPTION_DAYS_PER_MONTH,
    OrderStatus,
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
        plan=plan_config.plan_code,
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
        "months": months,
        "plan_name": plan_config.name,
        "plan_code": plan_config.plan_code,
        "monthly_price": plan_config.monthly_price,
        "plan_currency": plan_config.currency,
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


async def handle_subscription_callback(db: AsyncSession, payload: dict) -> bool:

    order_no = payload["merchant_order_no"]
    payment_status = payload["status"]

    oqs = await db.execute(select(Order).where(Order.order_no == order_no))
    order: Order = oqs.scalar_one_or_none()
    if not order:
        logger.error(f"订单不存在：{order_no=} {payload=}")
        return False
    if order.status == OrderStatus.paid:
        logger.warning(f"订单已处理过：{order_no=}")
        return True
    if order.status != OrderStatus.pending:
        logger.error(f"订单状态异常：{order_no=} status={order.status}")
        return False

    uqs = await db.execute(select(User).where(User.id == order.user_id))
    user: User = uqs.scalar_one_or_none()
    if not user:
        logger.error(f"用户不存在：user_id={order.user_id} {payload=}")
        return False

    pqs = await db.execute(
        select(SubscriptionPlanConfig).where(
            SubscriptionPlanConfig.id == order.product_id,
            SubscriptionPlanConfig.is_active.is_(True),
        )
    )
    plan_config: SubscriptionPlanConfig = pqs.scalar_one_or_none()
    if not plan_config:
        logger.error(f"订阅计划不存在：plan_config_id={order.product_id} {payload=}")
        return False

    if payment_status != "succeeded":
        # 更新订单状态
        order.status = OrderStatus.failed
        db.add(order)
        await db.flush()
        return True

    else:
        # 更新订单状态
        order.status = OrderStatus.paid
        db.add(order)
        await db.flush()

        # 计算订阅到期时间
        now = tz_now()

        # 如果用户当前订阅未过期，从原到期时间续期；否则从现在开始
        if user.subscription_ends_at and user.subscription_ends_at > now:
            ends_at = user.subscription_ends_at + timedelta(
                days=SUBSCRIPTION_DAYS_PER_MONTH * order.quantity
            )
        else:
            ends_at = now + timedelta(days=SUBSCRIPTION_DAYS_PER_MONTH * order.quantity)

        # 更新用户订阅
        user.subscription_plan_id = plan_config.id
        user.subscription_ends_at = ends_at
        db.add(user)
        await db.flush()

        # 增加账户积分
        acc = await get_or_create_account(db, user.id)
        credits_added = plan_config.monthly_credits * order.quantity
        acc.balance += credits_added
        db.add(acc)
        await db.flush()

        # 记录积分流水
        tx = CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.subscription,
            amount=credits_added,
            ref_type="subscription",
            ref_id=f"{plan_config.plan_code}_{order.quantity}m",
            note=f"订阅{plan_config.name}{order.quantity}个月赠送积分",
        )
        db.add(tx)
        return True

    # return UpgradeSubscriptionOut(
    #     plan=plan,
    #     ends_at=format_datetime(ends_at),
    #     credits_added=credits_added,
    # )
