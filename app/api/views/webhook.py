"""Stripe Webhook 处理器"""

from __future__ import annotations

import stripe
from fastapi import Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.routers import webhook_router as router
from app.core.deps import get_db
from app.core.config import settings
from app.api.services.stripe_service import StripeService


@router.post("/stripe", summary="Stripe Webhook 回调")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    处理 Stripe Webhook 事件

    ### 功能说明
    - 接收 Stripe 发送的支付事件通知
    - 验证 Webhook 签名确保安全性
    - 处理支付成功/失败事件

    ### 支持的事件类型
    - `payment_intent.succeeded`: 支付成功
    - `payment_intent.payment_failed`: 支付失败

    ### 注意事项
    - 此接口不需要认证（Stripe 服务器直接调用）
    - 必须配置 Webhook 签名密钥（STRIPE_WEBHOOK_SECRET）
    - 在 Stripe Dashboard 中配置 Webhook URL
    """
    if not settings.stripe_webhook_secret:
        logger.error("Stripe Webhook Secret 未配置")
        raise HTTPException(status_code=500, detail="Webhook 未配置")

    # 获取原始请求体
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.error("缺少 Stripe 签名头")
        raise HTTPException(status_code=400, detail="缺少签名")

    try:
        # 验证 Webhook 签名
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        # 无效的 payload
        logger.error(f"无效的 Webhook payload: {e}")
        raise HTTPException(status_code=400, detail="无效的 payload")
    except stripe.error.SignatureVerificationError as e:
        # 签名验证失败
        logger.error(f"Webhook 签名验证失败: {e}")
        raise HTTPException(status_code=400, detail="签名验证失败")

    # 记录事件（防止重复处理）
    is_new_event = await StripeService.record_webhook_event(
        db, event["id"], event["type"], event
    )

    if not is_new_event:
        logger.info(f"Webhook 事件已处理过: {event['id']}")
        return {"status": "success", "message": "事件已处理"}

    # 处理不同类型的事件
    event_type = event["type"]
    logger.info(f"收到 Stripe Webhook 事件: {event_type}")

    try:
        if event_type == "payment_intent.succeeded":
            # 支付成功
            payment_intent = event["data"]["object"]
            await StripeService.handle_payment_succeeded(db, payment_intent["id"])
            logger.info(f"支付成功事件处理完成: {payment_intent['id']}")

        elif event_type == "payment_intent.payment_failed":
            # 支付失败
            payment_intent = event["data"]["object"]
            await StripeService.handle_payment_failed(db, payment_intent["id"])
            logger.info(f"支付失败事件处理完成: {payment_intent['id']}")

        else:
            # 其他事件类型（暂不处理）
            logger.info(f"未处理的事件类型: {event_type}")

    except Exception as e:
        logger.error(f"处理 Webhook 事件失败: {e}", exc_info=True)
        # 即使处理失败，也返回 200，避免 Stripe 重试
        # 可以在数据库中记录错误，后续手动处理

    return {"status": "success"}

