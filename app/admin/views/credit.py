"""积分管理相关路由"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.responses import success_response
from app.core.schemas import Response, RechargeIn
from app.core.deps import get_db, get_current_user
from app.routers import admin_credit_router as router
from app.admin.controller.credits import recharge_user_credits


@router.post("/recharge", summary="管理员充值积分", response_model=Response[dict])
async def recharge_credits(
    payload: RechargeIn,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_user),
):
    """
    管理员为用户充值积分

    ### 功能说明
    - 为指定用户增加积分余额
    - 记录充值流水
    - 支持自定义备注说明

    ### 权限要求
    - **仅限管理员**使用
    - 需要在请求头中携带管理员的访问令牌

    ### 充值流程
    1. 验证管理员权限
    2. 查找目标用户的积分账户
    3. 增加积分余额
    4. 记录充值流水
    5. 返回充值结果

    ### 使用场景
    - 用户反馈问题补偿
    - 促销活动赠送
    - 测试账号充值
    - 特殊情况调整

    ### 安全提示
    充值操作会被记录在积分流水中，可追溯审计。
    """
    # 为用户充值（如用户不存在会抛出异常）
    result = await recharge_user_credits(
        db, payload.user_id, payload.amount, payload.note
    )

    return success_response("充值成功", result)
