"""
支付网关客户端

与支付网关进行通信,处理支付、退款等操作
"""

from __future__ import annotations

import hmac
import json
import enum
import hashlib
import traceback
from uuid import UUID
from datetime import datetime
from typing import Any, Literal
from dataclasses import dataclass

import httpx
from loguru import logger

from app.core.constants import OrderStatus


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


@dataclass
class PaymentResult:
    """支付创建结果"""

    payment_id: str  # 支付网关返回的支付ID
    merchant_order_no: str  # 商户订单号
    status: str  # 支付状态
    type: Literal["redirect", "form", "qr", "client_secret"]  # 返回类型
    payload: dict[str, Any]  # 类型对应的payload


@dataclass
class PaymentDetailResult:
    """支付详情查询结果"""

    id: UUID
    merchant_order_no: str
    provider: str
    amount: int
    currency: str
    status: str
    provider_txn_id: str | None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None


@dataclass
class RefundResult:
    """退款结果"""

    id: UUID
    payment_id: UUID
    refund_amount: int
    reason: str | None
    status: str
    provider: str
    provider_refund_id: str | None
    created_at: datetime
    updated_at: datetime
    refunded_at: datetime | None


class PaymentGatewayError(Exception):
    """支付网关错误"""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class PaymentGatewayClient:
    """
    支付网关客户端

    负责与支付网关进行通信,封装所有支付相关的操作。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 180,
    ):
        """
        初始化支付网关客户端

        Args:
            base_url: 支付网关 API 地址
            api_key: API密钥
            timeout: 请求超时时间(秒)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        logger.info(f"初始化支付网关客户端: base_url={base_url}")

    async def create_payment(
        self,
        merchant_order_no: str,
        provider: str,
        currency: str,
        quantity: int,
        unit_amount: int,
        product_name: str,
        product_desc: str,
        notify_url: str | None = None,
        expire_minutes: int | None = None,
        **kwargs: Any,
    ) -> PaymentResult:
        """
        创建支付

        Args:
            merchant_order_no: 商户订单号
            provider: 支付渠道 (stripe/alipay/wechat)
            currency: 货币代码（如 USD, CNY）
            quantity: 数量
            unit_amount: 单价（最小货币单位，如分）
            product_name: 商品名称
            product_desc: 商品描述
            notify_url: 回调通知 URL（Stripe 使用 webhook）
            expire_minutes: 过期时间（Stripe Session 默认 24 小时）
            **kwargs: 额外参数
                - success_url: 支付成功跳转 URL
                - cancel_url: 取消支付跳转 URL
                - metadata: 额外的元数据

        Returns:
            支付创建结果

        Raises:
            PaymentGatewayError: 创建失败时抛出
        """
        logger.info(
            f"[PaymentGateway] 创建支付: order_no={merchant_order_no}, "
            f"provider={provider}, unit_amount={unit_amount}, quantity={quantity}, "
            f"currency={currency}"
        )

        request_data = {
            "merchant_order_no": merchant_order_no,
            "currency": currency,
            "provider": provider,
            "quantity": quantity,
            "unit_amount": unit_amount,
            "product_name": product_name,
            "product_desc": product_desc,
        }

        if notify_url:
            request_data["notify_url"] = notify_url
        if expire_minutes:
            request_data["expire_minutes"] = expire_minutes

        # 添加额外参数
        if "success_url" in kwargs:
            request_data["success_url"] = kwargs["success_url"]
        if "cancel_url" in kwargs:
            request_data["cancel_url"] = kwargs["cancel_url"]
        if "metadata" in kwargs:
            request_data["metadata"] = kwargs["metadata"]

        try:
            response = await self._request("POST", "/v1/payments", request_data)

            return PaymentResult(
                payment_id=response["payment_id"],
                merchant_order_no=response["merchant_order_no"],
                status=response["status"],
                type=response["type"],
                payload=response["payload"],
            )
        except Exception as e:
            logger.error(f"[PaymentGateway] 创建支付失败: {traceback.format_exc()}")
            raise PaymentGatewayError("CREATE_PAYMENT_FAILED", str(e))

    async def get_payment(self, payment_id: UUID | str) -> PaymentDetailResult:
        """
        查询支付详情

        Args:
            payment_id: 支付ID

        Returns:
            支付详情

        Raises:
            PaymentGatewayError: 查询失败时抛出
        """
        logger.info(f"[PaymentGateway] 查询支付: payment_id={payment_id}")

        try:
            response = await self._request("GET", f"/v1/payments/{payment_id}")

            return PaymentDetailResult(
                id=UUID(response["id"]),
                merchant_order_no=response["merchant_order_no"],
                provider=response["provider"],
                amount=response["amount"],
                currency=response["currency"],
                status=response["status"],
                provider_txn_id=response.get("provider_txn_id"),
                created_at=datetime.fromisoformat(response["created_at"]),
                updated_at=datetime.fromisoformat(response["updated_at"]),
                paid_at=(
                    datetime.fromisoformat(response["paid_at"])
                    if response.get("paid_at")
                    else None
                ),
            )
        except Exception as e:
            logger.error(f"[PaymentGateway] 查询支付失败: {traceback.format_exc()}")
            raise PaymentGatewayError("GET_PAYMENT_FAILED", str(e))

    async def cancel_payment(
        self,
        merchant_order_no: str,
        payment_id: UUID | str,
    ) -> bool:
        """
        取消支付订单

        Args:
            merchant_order_no: 商户订单号
            payment_id: 支付ID

        Returns:
            是否取消成功（code == 0）

        Raises:
            PaymentGatewayError: 取消失败时抛出
        """
        logger.info(
            f"[PaymentGateway] 取消支付: order_no={merchant_order_no}, "
            f"payment_id={payment_id}"
        )

        request_data = {
            "merchant_order_no": merchant_order_no,
            "payment_id": str(payment_id),
        }

        url = f"{self.base_url}/v1/payments/cancel"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=request_data)

                if response.status_code >= 400:
                    error_data = response.json() if response.text else {}
                    error_message = error_data.get(
                        "message", response.text or "Unknown error"
                    )
                    raise PaymentGatewayError(
                        f"HTTP_{response.status_code}",
                        error_message,
                        error_data,
                    )

                response_json = response.json() if response.text else {}
                return response_json.get("code") == 0
        except httpx.HTTPError as e:
            logger.error(f"[PaymentGateway] HTTP 请求失败: {traceback.format_exc()}")
            raise PaymentGatewayError("HTTP_REQUEST_FAILED", str(e))
        except Exception as e:
            logger.error(f"[PaymentGateway] 取消支付失败: {traceback.format_exc()}")
            raise PaymentGatewayError("CANCEL_PAYMENT_FAILED", str(e))

    async def create_refund(
        self,
        payment_id: UUID | str,
        refund_amount: int | None = None,
        reason: str | None = None,
        notify_url: str | None = None,
    ) -> RefundResult:
        """
        创建退款

        Args:
            payment_id: 支付ID
            refund_amount: 退款金额(最小货币单位,不填则全额退款)
            reason: 退款原因
            notify_url: 退款回调通知地址

        Returns:
            退款结果

        Raises:
            PaymentGatewayError: 退款失败时抛出
        """
        logger.info(
            f"[PaymentGateway] 创建退款: payment_id={payment_id}, "
            f"amount={refund_amount}, reason={reason}"
        )

        request_data = {"payment_id": str(payment_id)}
        if refund_amount is not None:
            request_data["refund_amount"] = refund_amount
        if reason:
            request_data["reason"] = reason
        if notify_url:
            request_data["notify_url"] = notify_url

        try:
            response = await self._request("POST", "/v1/refunds", request_data)

            return RefundResult(
                id=UUID(response["id"]),
                payment_id=UUID(response["payment_id"]),
                refund_amount=response["refund_amount"],
                reason=response.get("reason"),
                status=response["status"],
                provider=response["provider"],
                provider_refund_id=response.get("provider_refund_id"),
                created_at=datetime.fromisoformat(response["created_at"]),
                updated_at=datetime.fromisoformat(response["updated_at"]),
                refunded_at=(
                    datetime.fromisoformat(response["refunded_at"])
                    if response.get("refunded_at")
                    else None
                ),
            )
        except Exception as e:
            logger.error(f"[PaymentGateway] 创建退款失败: {traceback.format_exc()}")
            raise PaymentGatewayError("CREATE_REFUND_FAILED", str(e))

    async def get_refund(self, refund_id: UUID | str) -> RefundResult:
        """
        查询退款详情

        Args:
            refund_id: 退款ID

        Returns:
            退款详情

        Raises:
            PaymentGatewayError: 查询失败时抛出
        """
        logger.info(f"[PaymentGateway] 查询退款: refund_id={refund_id}")

        try:
            response = await self._request("GET", f"/v1/refunds/{refund_id}")

            return RefundResult(
                id=UUID(response["id"]),
                payment_id=UUID(response["payment_id"]),
                refund_amount=response["refund_amount"],
                reason=response.get("reason"),
                status=response["status"],
                provider=response["provider"],
                provider_refund_id=response.get("provider_refund_id"),
                created_at=datetime.fromisoformat(response["created_at"]),
                updated_at=datetime.fromisoformat(response["updated_at"]),
                refunded_at=(
                    datetime.fromisoformat(response["refunded_at"])
                    if response.get("refunded_at")
                    else None
                ),
            )
        except Exception as e:
            logger.error(f"[PaymentGateway] 查询退款失败: {traceback.format_exc()}")
            raise PaymentGatewayError("GET_REFUND_FAILED", str(e))

    def verify_callback_signature(
        self, payload: dict, signature: str, secret: str
    ) -> bool:
        """
        验证支付网关回调签名

        Args:
            payload: 回调数据
            signature: 签名
            secret: 密钥

        Returns:
            是否验证通过
        """
        # 这里需要根据支付网关的签名算法来实现
        # 示例:使用HMAC-SHA256
        try:
            payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected_signature = hmac.new(
                secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            logger.error(f"[PaymentGateway] 验证签名失败: {traceback.format_exc()}")
            return False

    async def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        """
        发送 HTTP 请求到支付网关

        Args:
            method: HTTP 方法
            path: API 路径
            data: 请求数据

        Returns:
            响应数据

        Raises:
            PaymentGatewayError: 请求失败时抛出
        """
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"不支持的 HTTP 方法: {method}")

                # 检查响应状态
                if response.status_code >= 400:
                    error_data = response.json() if response.text else {}
                    error_message = error_data.get(
                        "message", response.text or "Unknown error"
                    )
                    raise PaymentGatewayError(
                        f"HTTP_{response.status_code}",
                        error_message,
                        error_data,
                    )

                return response.json()["data"]

        except httpx.HTTPError as e:
            logger.error(f"[PaymentGateway] HTTP 请求失败: {traceback.format_exc()}")
            raise PaymentGatewayError("HTTP_REQUEST_FAILED", str(e))


# 全局客户端实例(懒加载)
_client: PaymentGatewayClient | None = None


def get_payment_gateway_client() -> PaymentGatewayClient:
    """
    获取支付网关客户端实例

    Returns:
        支付网关客户端

    Raises:
        ValueError: 配置缺失时抛出
    """
    global _client

    if _client is None:
        from app.core.config import settings

        if not settings.payment_gateway_url:
            raise ValueError("支付网关 URL 未配置 (payment_gateway_url)")
        if not settings.payment_gateway_app_id:
            raise ValueError("支付网关 App ID 未配置 (payment_gateway_app_id)")

        _client = PaymentGatewayClient(
            base_url=settings.payment_gateway_url,
            api_key=settings.payment_gateway_app_id,
        )

    return _client


def map_payment_status_to_order_status(payment_status: str) -> OrderStatus:
    """
    将支付网关的支付状态映射到订单状态

    Args:
        payment_status: 支付网关的支付状态

    Returns:
        订单状态
    """
    # 严格对齐支付网关状态（不做兼容）：pending / succeeded / failed / canceled
    # 注意：业务订单状态有 paid/fulfilled 等语义，因此这里做最小必要映射。
    status_map = {
        PaymentStatus.pending.value: OrderStatus.pending,
        PaymentStatus.succeeded.value: OrderStatus.paid,
        PaymentStatus.failed.value: OrderStatus.failed,
        PaymentStatus.canceled.value: OrderStatus.cancelled,
    }
    return status_map.get(payment_status.lower(), OrderStatus.failed)
