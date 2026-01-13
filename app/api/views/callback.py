"""支付回调相关路由"""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends, Request, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.config import settings
from app.core.responses import success_response
from app.routers import callback_router as router
from app.core.deps import get_db
from app.core.schemas import Response
from app.api.controller.orders import handle_payment_callback
from app.api.services.payment_gateway_client import get_payment_gateway_client


@router.post(
    "/payment-gateway",
    summary="支付网关回调",
    response_model=Response[dict],
)
async def payment_gateway_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gateway_signature: str | None = Header(None, alias="X-Gateway-Signature"),
):
    """
    接收支付网关的支付结果回调

    ### 功能说明
    - 接收支付网关发送的支付结果通知
    - 验证回调签名确保安全性
    - 更新订单状态并执行业务处理

    ### 回调数据格式
    支付网关会以 JSON 格式发送以下数据：
    ```json
    {
      "event_type": "payment.succeeded" | "payment.failed" | "payment.cancelled",
      "event_id": "evt_xxx",
      "created_at": "2024-01-01T00:00:00Z",
      "data": {
        "payment_id": "pay_xxx",
        "merchant_order_no": "order_xxx",
        "amount": 1000,
        "currency": "USD",
        "status": "succeeded",
        "provider_txn_id": "txn_xxx",
        "paid_at": "2024-01-01T00:00:00Z"
      }
    }
    ```

    ### 签名验证
    - 签名通过 HTTP Header `X-Gateway-Signature` 传递
    - 签名算法由支付网关客户端实现
    - 验证失败会返回 401 错误

    ### 幂等性
    - 同一个订单的回调可能会多次调用
    - 系统会自动处理重复回调，确保业务只执行一次

    ### 注意事项
    - 此接口不需要用户认证
    - 仅供支付网关调用
    - 生产环境必须配置签名密钥
    """
    # 获取请求体
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"解析回调请求体失败: {e}")
        raise HTTPException(status_code=400, detail="无效的请求体")

    logger.info(
        f"收到支付网关回调: event_type={payload.get('event_type')}, "
        f"event_id={payload.get('event_id')}"
    )

    # 验证签名
    if (
        hasattr(settings, "payment_callback_secret")
        and settings.payment_callback_secret
    ):
        if not x_gateway_signature:
            logger.error("缺少签名header")
            raise HTTPException(status_code=401, detail="缺少签名")

        try:
            payment_client = get_payment_gateway_client()
            is_valid = payment_client.verify_callback_signature(
                payload=payload,
                signature=x_gateway_signature,
                secret=settings.payment_callback_secret,
            )

            if not is_valid:
                logger.error(
                    f"支付回调签名验证失败: event_id={payload.get('event_id')}"
                )
                raise HTTPException(status_code=401, detail="签名验证失败")

        except Exception as e:
            logger.error(f"签名验证异常: {e}")
            raise HTTPException(status_code=401, detail="签名验证失败")
    else:
        logger.warning("未配置支付回调签名密钥，跳过签名验证（仅限开发环境）")

    # 解析回调数据
    event_type = payload.get("event_type", "")
    data = payload.get("data", {})

    merchant_order_no = data.get("merchant_order_no")
    payment_id = data.get("payment_id")
    status = data.get("status")

    if not merchant_order_no or not payment_id or not status:
        logger.error(f"回调数据缺少必要字段: {payload}")
        raise HTTPException(status_code=400, detail="回调数据不完整")

    # 解析支付金额（最小货币单位转为标准单位）
    paid_amount = None
    if "amount" in data and "currency" in data:
        amount_cents = data["amount"]
        currency = data["currency"]
        # 转换为标准金额
        if currency.upper() in ["USD", "EUR", "GBP", "CNY"]:
            paid_amount = amount_cents / 100
        elif currency.upper() in ["JPY", "KRW"]:
            paid_amount = float(amount_cents)
        else:
            paid_amount = amount_cents / 100

    # 解析支付时间
    paid_at = None
    if data.get("paid_at"):
        try:
            paid_at = datetime.fromisoformat(data["paid_at"].replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"无法解析支付时间: {data.get('paid_at')}")

    # 处理回调
    try:
        order = await handle_payment_callback(
            db=db,
            order_id=merchant_order_no,
            payment_id=payment_id,
            status=status,
            paid_amount=paid_amount,
            paid_at=paid_at,
            error_message=data.get("error_message"),
        )

        logger.info(
            f"处理支付回调成功: order_id={order.order_no}, "
            f"status={order.status.value}, event_id={payload.get('event_id')}"
        )

        return success_response(
            "处理成功",
            {
                "order_id": order.order_no,
                "status": order.status.value,
                "event_id": payload.get("event_id"),
            },
        )

    except Exception as e:
        logger.error(f"处理支付回调失败: {e}", exc_info=True)
        # 返回 200 避免支付网关重试（错误已记录，可后续手动处理）
        return success_response(
            "处理失败",
            {
                "order_id": merchant_order_no,
                "event_id": payload.get("event_id"),
                "error": str(e),
            },
        )


@router.post(
    "/refund-gateway",
    summary="支付网关退款回调",
    response_model=Response[dict],
)
async def refund_gateway_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gateway_signature: str | None = Header(None, alias="X-Gateway-Signature"),
):
    """
    接收支付网关的退款结果回调

    ### 功能说明
    - 接收支付网关发送的退款结果通知
    - 验证回调签名确保安全性
    - 更新退款状态

    ### 回调数据格式
    ```json
    {
      "event_type": "refund.succeeded" | "refund.failed",
      "event_id": "evt_xxx",
      "created_at": "2024-01-01T00:00:00Z",
      "data": {
        "refund_id": "ref_xxx",
        "payment_id": "pay_xxx",
        "amount": 1000,
        "status": "succeeded",
        "provider_refund_id": "ref_provider_xxx",
        "refunded_at": "2024-01-01T00:00:00Z"
      }
    }
    ```

    ### 注意事项
    - 退款通常是异步处理的，可能需要几分钟到几天
    - 此回调用于通知退款最终状态
    """
    # 获取请求体
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"解析退款回调请求体失败: {e}")
        raise HTTPException(status_code=400, detail="无效的请求体")

    logger.info(
        f"收到退款回调: event_type={payload.get('event_type')}, "
        f"event_id={payload.get('event_id')}"
    )

    # 验证签名
    if (
        hasattr(settings, "payment_callback_secret")
        and settings.payment_callback_secret
    ):
        if not x_gateway_signature:
            logger.error("缺少签名header")
            raise HTTPException(status_code=401, detail="缺少签名")

        try:
            payment_client = get_payment_gateway_client()
            is_valid = payment_client.verify_callback_signature(
                payload=payload,
                signature=x_gateway_signature,
                secret=settings.payment_callback_secret,
            )

            if not is_valid:
                logger.error(
                    f"退款回调签名验证失败: event_id={payload.get('event_id')}"
                )
                raise HTTPException(status_code=401, detail="签名验证失败")

        except Exception as e:
            logger.error(f"签名验证异常: {e}")
            raise HTTPException(status_code=401, detail="签名验证失败")
    else:
        logger.warning("未配置支付回调签名密钥，跳过签名验证（仅限开发环境）")

    data = payload.get("data", {})
    refund_id = data.get("refund_id")
    status = data.get("status")

    logger.info(
        f"退款回调处理: refund_id={refund_id}, status={status}, "
        f"event_id={payload.get('event_id')}"
    )

    # 这里可以根据需要更新退款状态
    # 目前仅记录日志，实际业务可能需要更新数据库

    return success_response(
        "处理成功",
        {
            "refund_id": refund_id,
            "status": status,
            "event_id": payload.get("event_id"),
        },
    )
