"""支付网关回调处理器"""

from __future__ import annotations

import traceback
import hmac
import json
import hashlib

from loguru import logger
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.config import settings
from app.routers import callback_router as router
from app.core.responses import success_response, error_response, CommonError
from app.api.controller.orders import handle_payment_callback, handle_refund_callback


def _extract_signature(request: Request, payload: dict) -> str | None:
    # 兼容：签名既可能在 header，也可能在 body（schemas.PaymentCallbackIn.signature）
    return (
        request.headers.get("x-signature")
        or request.headers.get("X-Signature")
        or request.headers.get("x-payment-signature")
        or request.headers.get("X-Payment-Signature")
        or payload.get("signature")
    )


def _verify_callback_signature_or_reject(request: Request, payload: dict) -> bool:
    """
    回调验签：若配置了 settings.payment_callback_secret 则强制验证；
    未配置时为了兼容旧环境只记录告警（但这会降低安全性）。

    注意：计算签名时必须排除 payload 内的 signature 字段本身。
    """
    secret = settings.payment_callback_secret
    if not secret:
        logger.warning(
            "payment_callback_secret 未配置：回调验签被跳过（存在被伪造回调的风险）"
        )
        return True

    signature = _extract_signature(request, payload)
    if not signature:
        return False

    signed_payload = dict(payload)
    signed_payload.pop("signature", None)

    # 与 PaymentGatewayClient.verify_callback_signature 保持一致：
    # json.dumps(sort_keys=True, separators=(",", ":")) + HMAC-SHA256(hex)
    try:
        payload_str = json.dumps(signed_payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            str(secret).encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, str(signature))
    except Exception:
        logger.error(f"回调签名计算/校验失败: {traceback.format_exc()}")
        return False


@router.post("/payment", summary="支付网关-支付回调")
async def payment_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception as _:
        logger.error(f"解析支付回调请求体失败: {traceback.format_exc()}")
        return error_response(CommonError.BAD_REQUEST, "无效请求体")

    try:
        if not _verify_callback_signature_or_reject(request, payload):
            return error_response(CommonError.FORBIDDEN, "回调签名验证失败")

        is_success = await handle_payment_callback(db, payload)
        await db.commit()
    except Exception as _:
        logger.error(f"支付回调处理失败: {traceback.format_exc()}")
        await db.rollback()
        return error_response(CommonError.INTERNAL_ERROR, "支付回调处理失败")

    if is_success:
        return success_response()
    else:
        # 回调内容不符合预期（缺字段/未知状态），视为 400（通常无需重试）
        return error_response(CommonError.BAD_REQUEST, "回调内容不被接受")


@router.post("/refund", summary="支付网关-退款回调")
async def refund_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception as _:
        logger.error(f"解析退款回调请求体失败: {traceback.format_exc()}")
        return error_response(CommonError.BAD_REQUEST, "无效请求体")

    try:
        if not _verify_callback_signature_or_reject(request, payload):
            return error_response(CommonError.FORBIDDEN, "回调签名验证失败")

        is_success = await handle_refund_callback(db, payload)
        await db.commit()
    except Exception as _:
        logger.error(f"退款回调处理失败: {traceback.format_exc()}")
        await db.rollback()
        return error_response(CommonError.INTERNAL_ERROR, "退款回调处理失败")

    if is_success:
        return success_response()
    else:
        return error_response(CommonError.BAD_REQUEST, "回调内容不被接受")
