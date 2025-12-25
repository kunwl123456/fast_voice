"""订阅管理相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.responses import success_response, bad_request_response
from app.deps import get_db, require_console_user
from app.controller.subscription import (
    get_user_subscription,
    upgrade_user_subscription,
    validate_plan,
    SubscriptionPlanType,
)
from app.schemas import Response, SubscriptionInfo, UpgradeSubscriptionIn

router = APIRouter(prefix="/console", tags=["订阅管理"])


@router.get(
    "/subscription", summary="获取订阅信息", response_model=Response[SubscriptionInfo]
)
async def get_subscription(user: User = Depends(require_console_user)):
    """
    获取当前用户的订阅计划信息

    ### 功能说明
    - 查询当前订阅计划
    - 获取订阅状态和到期时间
    - 获取计划的功能特性列表
    """
    subscription_data = await get_user_subscription(user)
    return success_response("获取成功", subscription_data.model_dump())


@router.post("/subscription/upgrade", summary="升级订阅", response_model=Response[dict])
async def upgrade_subscription(
    payload: UpgradeSubscriptionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
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
    if not validate_plan(payload.plan):
        return bad_request_response(
            "无效的订阅计划", {"valid_plans": SubscriptionPlanType.can_upgrade_plans()}
        )

    result = await upgrade_user_subscription(db, user, payload.plan, payload.months)
    return success_response("订阅升级成功", result)
