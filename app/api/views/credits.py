"""积分管理相关路由"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.routers import credits_router as router
from app.core.responses import success_response
from app.core.deps import get_db, require_console
from app.core.schemas import (
    Response,
    CreditAccountOut,
    CreditTxOut,
    CreditPackageOut,
    BuyCreditIn,
    BuyCreditOut,
)
from app.api.controller.credits import (
    get_user_credit_balance,
    get_user_credit_transactions,
    list_credit_packages,
    buy_credits,
)


@router.get("", summary="获取积分余额", response_model=Response[CreditAccountOut])
async def get_credits(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console)
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
    "/transactions",
    summary="积分交易记录",
    response_model=Response[list[CreditTxOut]],
)
async def credit_transactions(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console)
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


@router.get(
    "/packages",
    summary="获取积分充值档位",
    response_model=Response[list[CreditPackageOut]],
)
async def get_credit_packages(db: AsyncSession = Depends(get_db)):
    packages = await list_credit_packages(db)
    return success_response("获取成功", [p.model_dump() for p in packages])


@router.post(
    "/buy",
    summary="购买积分（创建支付订单）",
    response_model=Response[BuyCreditOut],
)
async def buy_credit_package(
    payload: BuyCreditIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console),
):
    result = await buy_credits(db, user, payload)
    return success_response("创建订单成功", result.model_dump())
