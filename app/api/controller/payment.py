"""
支付控制器

处理支付相关的业务逻辑
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.config import settings
from app.core.schemas import (
    CreatePaymentIntentIn,
    CreatePaymentIntentOut,
    PaymentStatusOut,
    PaymentHistoryOut,
    StripeConfigOut,
)
from app.core.exceptions import BadRequestException
from app.api.services.stripe_service import StripeService


async def create_payment_intent(
    db: AsyncSession, user: User, payload: CreatePaymentIntentIn
) -> CreatePaymentIntentOut:
    """
    创建支付意图

    Args:
        db: 数据库会话
        user: 当前用户
        payload: 支付请求参数

    Returns:
        支付意图信息
    """
    if not settings.stripe_secret_key or not settings.stripe_publishable_key:
        raise BadRequestException("Stripe 支付未配置，请联系管理员")

    # 创建支付意图
    payment, client_secret = await StripeService.create_payment_intent(
        db=db,
        user=user,
        payment_type=payload.payment_type,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=payload.payment_method,
        credits_amount=payload.credits_amount,
        subscription_plan=payload.subscription_plan,
        subscription_months=payload.subscription_months,
    )

    return CreatePaymentIntentOut(
        payment_id=payment.uuid,
        client_secret=client_secret,
        publishable_key=settings.stripe_publishable_key,
        amount=payment.amount,
        currency=payment.currency,
        return_url=settings.stripe_payment_return_url,
    )


async def get_payment_status(
    db: AsyncSession, user: User, payment_id: str
) -> PaymentStatusOut:
    """
    查询支付状态

    Args:
        db: 数据库会话
        user: 当前用户
        payment_id: 支付订单ID

    Returns:
        支付状态信息
    """
    payment = await StripeService.get_payment_by_uuid(db, payment_id)

    # 验证支付订单属于当前用户
    if payment.user_id != user.id:
        raise BadRequestException("无权访问此支付订单")

    return PaymentStatusOut(
        payment_id=payment.uuid,
        status=payment.status.value,
        payment_type=payment.payment_type.value,
        amount=payment.amount,
        currency=payment.currency,
        credits_amount=payment.credits_amount,
        subscription_plan=payment.subscription_plan.value
        if payment.subscription_plan
        else None,
        subscription_months=payment.subscription_months,
        error_message=payment.error_message,
        created_at=payment.created_at,
        completed_at=payment.completed_at,
    )


async def get_payment_history(db: AsyncSession, user: User) -> list[PaymentHistoryOut]:
    """
    获取支付历史

    Args:
        db: 数据库会话
        user: 当前用户

    Returns:
        支付历史列表
    """
    payments = await StripeService.get_user_payments(db, user.id)

    return [
        PaymentHistoryOut(
            payment_id=payment.uuid,
            payment_type=payment.payment_type.value,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status.value,
            credits_amount=payment.credits_amount,
            subscription_plan=payment.subscription_plan.value
            if payment.subscription_plan
            else None,
            subscription_months=payment.subscription_months,
            created_at=payment.created_at,
            completed_at=payment.completed_at,
        )
        for payment in payments
    ]


def get_stripe_config() -> StripeConfigOut:
    """
    获取 Stripe 公开配置

    Returns:
        Stripe 配置信息
    """
    if not settings.stripe_publishable_key:
        raise BadRequestException("Stripe 支付未配置")

    return StripeConfigOut(
        publishable_key=settings.stripe_publishable_key, currency="usd"
    )

