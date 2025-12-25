"""订阅管理业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditTransaction, SubscriptionPlan, TxType, User
from app.services.billing import get_or_create_account
from app.subscription import get_plan_config, get_plan_features
from app.schemas import SubscriptionInfo


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
        if user.subscription_ends_at < datetime.now():
            status = "expired"

    return SubscriptionInfo(
        plan=user.subscription_plan.value,
        plan_name=plan_config.name,
        status=status,
        ends_at=user.subscription_ends_at,
        features=get_plan_features(user.subscription_plan.value),
    )


async def upgrade_user_subscription(
    db: AsyncSession, user: User, plan: str, months: int
) -> dict:
    """
    升级用户的订阅计划

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - plan: 目标订阅计划（pro/enterprise）
    - months: 订阅月数

    ### 返回
    - 升级结果字典（包含计划、到期时间、赠送积分）
    """
    # 计算订阅到期时间
    now = datetime.now()
    ends_at = now + timedelta(days=30 * months)

    # 更新用户订阅
    user.subscription_plan = SubscriptionPlan(plan)
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

    return {
        "plan": plan,
        "ends_at": ends_at,
        "credits_added": credits_added,
    }


def validate_plan(plan: str) -> bool:
    """
    验证订阅计划是否有效

    ### 参数
    - plan: 订阅计划代码

    ### 返回
    - 是否有效
    """
    return plan in ["pro", "enterprise"]
