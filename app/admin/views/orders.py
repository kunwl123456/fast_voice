"""订单管理相关路由"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.responses import success_response
from app.core.deps import get_db, get_current_user
from app.routers import admin_order_router as router
from app.core.schemas import (
    Response,
    OrderListOut,
    OrderDetailOut,
)
from app.api.controller.orders import (
    get_order_list,
    get_order_detail,
)


@router.get(
    "",
    summary="获取订单列表",
    response_model=Response[list[OrderListOut]],
)
async def list_orders(
    admin_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的订单列表

    ### 功能说明
    - 返回最近 50 条订单记录
    - 按创建时间倒序排列

    ### 订单状态说明
    - `pending`: 待支付
    - `paid`: 已支付（等待业务处理）
    - `fulfilled`: 已完成（业务处理完成）
    - `cancelled`: 已取消
    - `expired`: 已过期
    - `refunded`: 已退款
    """
    result = await get_order_list(db, user)
    return success_response("获取成功", [r.model_dump() for r in result])


@router.get(
    "/{order_id}",
    summary="获取订单详情",
    response_model=Response[OrderDetailOut],
)
async def get_order(
    order_id: str,
    admin_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定订单的详细信息

    ### 功能说明
    - 查询订单的完整信息
    - 包含支付状态、业务处理状态等
    - 只能查询自己的订单

    ### 使用场景
    - 支付后轮询订单状态
    - 查看订单详情
    """
    result = await get_order_detail(db, user=user, order_no=order_id)
    return success_response("获取成功", result.model_dump())
