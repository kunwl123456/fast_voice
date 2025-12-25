"""积分管理相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.responses import success_response, not_found_response
from app.deps import get_db, require_admin, require_console_user
from app.controller.credits import (
    get_user_credit_balance,
    get_user_credit_transactions,
    recharge_user_credits,
)
from app.schemas import Response, CreditAccountOut, CreditTxOut, RechargeIn

router = APIRouter(prefix="/console", tags=["积分管理"])


@router.get(
    "/credits", summary="获取积分余额", response_model=Response[CreditAccountOut]
)
async def get_credits(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """
    获取当前用户的积分账户余额

    ### 功能说明
    - 查询积分账户的可用余额
    - 如果账户不存在会自动创建

    ### 积分说明
    积分用途：
    - 调用 TTS 语音合成服务
    - 克隆音色
    - 其他付费功能

    获取积分的方式：
    - 注册赠送（免费版）
    - 订阅升级赠送
    - 管理员充值

    ### 使用场景
    - 查询可用积分
    - 判断是否需要充值
    - 监控积分消耗
    """
    credit_data = await get_user_credit_balance(db, user)
    return success_response("获取成功", credit_data.model_dump())


@router.get(
    "/credits/transactions",
    summary="积分交易记录",
    response_model=Response[list[CreditTxOut]],
)
async def credit_transactions(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """
    获取积分交易流水记录

    ### 功能说明
    - 查询所有积分变动记录
    - 包含收入和支出
    - 显示交易详情和原因

    ### 查询限制
    - 最多返回最近 200 条记录
    - 按时间倒序排列（最新的在前）

    ### 使用场景
    - 查看积分消费明细
    - 核对充值记录
    - 追踪积分流向
    - 账务对账
    """
    transactions_list = await get_user_credit_transactions(db, user)
    transactions_data = [t.model_dump() for t in transactions_list]
    return success_response("获取成功", transactions_data)


@router.post(
    "/admin/credits/recharge", summary="管理员充值积分", response_model=Response[dict]
)
async def recharge_credits(
    payload: RechargeIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
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
    recharge_user, result = await recharge_user_credits(
        db, payload.user_id, payload.amount, payload.note
    )
    if not recharge_user:
        return not_found_response("用户未找到", {"user_id": payload.user_id})

    return success_response("充值成功", result)
