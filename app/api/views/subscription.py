"""订阅管理相关路由"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.responses import success_response
from app.core.deps import get_db, require_console
from app.routers import subscription_router as router
from app.core.schemas import (
    Response,
    SubscriptionInfo,
    UpgradeSubscriptionIn,
    UpgradeSubscriptionOut,
    PlanConfigOut,
)
from app.api.controller.subscription import (
    get_user_subscription,
    upgrade_user_subscription,
    get_all_plan_configs,
)


@router.get("", summary="获取订阅信息", response_model=Response[SubscriptionInfo])
async def get_subscription(
    user: User = Depends(require_console),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的订阅计划信息

    ### 功能说明
    - 查询当前订阅计划
    - 获取订阅状态和到期时间
    - 获取剩余积分数
    """
    subscription_data = await get_user_subscription(user, db)
    return success_response("获取成功", subscription_data.model_dump())


@router.get(
    "/plans",
    summary="获取所有订阅计划配置",
    response_model=Response[list[PlanConfigOut]],
)
async def get_subscription_plans(db: AsyncSession = Depends(get_db)):
    """
    获取所有订阅计划的配置信息

    ### 功能说明
    - 返回所有可用订阅计划（free/pro/enterprise）
    - 包含每个计划的详细配置信息
    - 不需要登录即可访问

    ### 配置信息包括
    - monthly_credits: 每月赠送积分
    - monthly_quota: 月度请求配额
    - clone_limit: 克隆位限制（-1表示无限）
    - api_access: 是否提供API访问
    - commercial_use: 是否允许商业使用
    - priority_support: 是否提供优先支持
    """
    plans = await get_all_plan_configs(db)
    return success_response("获取成功", [plan.model_dump() for plan in plans])


@router.post(
    "/upgrade",
    summary="升级订阅",
    response_model=Response[UpgradeSubscriptionOut],
)
async def upgrade_subscription(
    payload: UpgradeSubscriptionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    """
    升级用户的订阅计划

    ### 功能说明
    - 升级到 Pro 或 Enterprise 订阅计划
    - 自动计算订阅到期时间
    - 赠送对应计划的月度积分
    - 记录积分流水

    ### 订阅周期
    - 按月订阅，可选择订阅月数（months 参数）
    - 每月按 30 天计算

    ### 积分赠送
    - 升级时立即获得 `monthly_credits × months` 的积分
    - 积分可用于调用 API 服务
    """
    result = await upgrade_user_subscription(
        db, user, payload.plan, payload.months, payload.pay_type
    )
    return success_response("订阅升级成功", result.model_dump())
