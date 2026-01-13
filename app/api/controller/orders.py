"""
订单控制器

处理订单相关的业务逻辑，作为前端与支付网关之间的桥梁
"""

from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    Currency,
    OrderType,
    OrderStatus,
    PaymentProvider,
    ORDER_EXPIRE_MINUTES,
)
from app.core.models import (
    User,
    Order,
)
from app.core.schemas import (
    CreateOrderIn,
    CreateOrderOut,
    OrderDetailOut,
    OrderListOut,
    CreateRefundIn,
    RefundOut,
)
from app.tools.common import tz_now
from app.core.error_codes import OrderError, RefundError
from app.api.services.plan_config import query_plan_config
from app.core.exceptions import BadRequestException, NotFoundException
from app.api.services.payment_gateway_client import (
    get_payment_gateway_client,
    PaymentGatewayError,
)


def _to_cents(amount: float, currency: str) -> int:
    """
    将金额转换为最小货币单位（如分）

    Args:
        amount: 金额
        currency: 货币类型

    Returns:
        最小货币单位金额
    """
    # USD、EUR等使用100，JPY等使用1
    if currency.upper() in ["USD", "EUR", "GBP", "CNY"]:
        return int(amount * 100)
    elif currency.upper() in ["JPY", "KRW"]:
        return int(amount)
    else:
        return int(amount * 100)  # 默认使用100


async def create_order(
    db: AsyncSession,
    user: User,
    payload: CreateOrderIn,
) -> CreateOrderOut:
    """
    创建业务订单

    Args:
        db: 数据库会话
        user: 当前用户
        payload: 创建订单请求

    Returns:
        创建订单响应
    """

    try:
        payment_provider = PaymentProvider(payload.payment_method)
    except ValueError:
        raise BadRequestException(error=OrderError.INVALID_PAYMENT_METHOD)

    try:
        order_type = OrderType(payload.order_type)
    except ValueError:
        raise BadRequestException(error=OrderError.INVALID_ORDER_TYPE)

    try:
        currency = Currency(payload.currency)
    except ValueError:
        raise BadRequestException(error=OrderError.INVALID_CURRENCY)

    # 计算订单过期时间
    expires_at = tz_now() + timedelta(minutes=ORDER_EXPIRE_MINUTES)

    # 创建订单记录
    amount = payload.unit_price * payload.quantity
    order = Order(
        user_id=user.id,
        order_type=order_type,
        product_id=payload.product_id,
        quantity=payload.quantity,
        amount=amount,
        currency=currency,
        status=OrderStatus.pending,
        payment_method=payment_provider,
        expires_at=expires_at,
        extra_metadata=payload.extra_metadata,
    )

    db.add(order)
    await db.flush()
    await db.refresh(order)

    # 调用支付网关创建支付订单
    try:
        payment_client = get_payment_gateway_client()

        # 构建回调通知地址
        notify_url = None
        if (
            hasattr(settings, "payment_gateway_callback_url")
            and settings.payment_callback_url
        ):
            notify_url = settings.payment_callback_url

        payment_result = await payment_client.create_payment(
            merchant_order_no=order.order_no,
            provider=payment_provider,
            currency=currency.upper(),
            quantity=payload.quantity,
            unit_amount=payload.unit_price,
            product_name=payload.product_name,
            product_desc=f"用户 {user.email} 购买 {payload.product_name}",
            notify_url=notify_url,
            expire_minutes=ORDER_EXPIRE_MINUTES,
            success_url=settings.payment_success_url,
            cancel_url=settings.payment_cancel_url,
            metadata={
                "customer_name": user.display_name,
                "customer_email": user.email,
                "merchant_order_no": order.order_no,
            },
        )

        # 更新订单的支付信息
        order.payment_id = str(payment_result.payment_id)

    except PaymentGatewayError as e:
        logger.error(f"支付网关创建订单失败: {e.code} - {e.message}")
        order.status = OrderStatus.failed
        em = order.extra_metadata or {}
        em["error_message"] = e.message
        order.extra_metadata = em
        await db.commit()
        raise BadRequestException(
            error=OrderError.FAILED_BY_CREATE_PAYMENT,
        )
    except Exception as e:
        logger.error(f"创建支付失败: {e}")
        order.status = OrderStatus.cancelled
        em = order.extra_metadata or {}
        em["error_message"] = str(e)
        order.extra_metadata = em
        await db.commit()
        raise BadRequestException(
            error=OrderError.FAILED_BY_CREATE_PAYMENT,
            message=f"创建支付失败: {e}",
        )

    await db.commit()
    await db.refresh(order)

    logger.info(
        f"创建订单成功: order_id={order.order_no}, user_id={user.id}, "
        f"type={order_type.value}, amount={amount}"
    )

    return CreateOrderOut(
        order_id=order.order_no,
        order_type=order.order_type.value,
        product_id=payload.product_id,
        product_name=payload.product_name,
        quantity=order.quantity,
        amount=order.amount,
        currency=order.currency,
        status=order.status.value,
        payment_id=str(order.payment_id),
        extra=payment_result.payload,
        expires_at=order.expires_at,
    )


async def get_order_detail(
    db: AsyncSession,
    order_no: str,
    user: User = None,
    check_creator: bool = True,
) -> OrderDetailOut:
    """
    获取订单详情

    Args:
        db: 数据库会话
        user: 当前用户
        order_no: 订单号
        check_creator: 是否校验用户

    Returns:
        订单详情
    """
    if check_creator:
        result = await db.execute(
            select(Order).where(Order.order_no == order_no, Order.user_id == user.id)
        )
    else:
        result = await db.execute(select(Order).where(Order.order_no == order_no))

    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundException(error=OrderError.ORDER_NOT_FOUND)

    # 订单展示名优先使用创建时写入的快照
    product_name = (order.extra_metadata or {}).get("product_name") or ""
    product_id = (order.extra_metadata or {}).get("product_id")
    if not product_id and order.subscription_plan_config:
        product_id = order.subscription_plan_config.plan_code

    return OrderDetailOut(
        order_id=order.order_no,
        order_type=order.order_type.value,
        product_id=product_id or "",
        product_name=product_name,
        quantity=order.quantity,
        amount=order.amount,
        currency=order.currency,
        status=order.status.value,
        payment_id=order.payment_id,
        payment_method=order.payment_method.value if order.payment_method else None,
        created_at=order.created_at,
        paid_at=order.paid_at,
        expires_at=order.expires_at,
    )


async def get_order_list(
    db: AsyncSession,
    user: User,
    limit: int = 50,
) -> list[OrderListOut]:
    """
    获取订单列表

    Args:
        db: 数据库会话
        user: 当前用户
        limit: 返回数量限制

    Returns:
        订单列表
    """
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    orders = result.scalars().all()

    return [
        OrderListOut(
            order_id=order.order_no,
            order_type=order.order_type.value,
            product_name=(order.extra_metadata or {}).get("product_name") or "",
            amount=order.amount,
            currency=order.currency,
            status=order.status.value,
            created_at=order.created_at,
        )
        for order in orders
    ]


async def cancel_order(
    db: AsyncSession,
    user: User,
    order_id: str,
) -> OrderDetailOut:
    """
    取消订单

    Args:
        db: 数据库会话
        user: 当前用户
        order_id: 订单ID

    Returns:
        订单详情
    """
    result = await db.execute(
        select(Order).where(Order.order_no == order_id, Order.user_id == user.id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise NotFoundException(error=OrderError.ORDER_NOT_FOUND)

    if order.status != OrderStatus.pending:
        raise BadRequestException(
            error=OrderError.CANNOT_CANCEL_ORDER,
            message=f"订单状态为 {order.status.value}，无法取消",
            data={"current_status": order.status.value},
        )

    order.status = OrderStatus.cancelled
    await db.commit()
    await db.refresh(order)

    logger.info(f"取消订单: order_id={order.order_no}")

    return await get_order_detail(db, order_no=order_id, user=user)


async def create_refund(
    db: AsyncSession,
    user: User,
    payload: CreateRefundIn,
) -> RefundOut:
    """
    创建退款

    Args:
        db: 数据库会话
        user: 当前用户
        payload: 退款请求

    Returns:
        退款响应
    """
    # 查找订单
    result = await db.execute(
        select(Order).where(
            Order.order_no == payload.order_id, Order.user_id == user.id
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        raise NotFoundException(error=OrderError.ORDER_NOT_FOUND)

    # 检查订单状态
    if order.status not in [OrderStatus.paid, OrderStatus.fulfilled]:
        raise BadRequestException(
            error=RefundError.CANNOT_REFUND_ORDER,
            message=f"订单状态为 {order.status.value}，无法退款。只有已支付或已完成的订单可以退款。",
            data={
                "current_status": order.status.value,
                "allowed_statuses": ["paid", "fulfilled"],
            },
        )

    if not order.payment_id:
        raise BadRequestException(error=RefundError.NO_PAYMENT_RECORD)

    # 调用支付网关创建退款
    try:
        payment_client = get_payment_gateway_client()

        # 如果指定了退款金额，需要验证
        refund_amount_cents = None
        if payload.refund_amount is not None:
            # 验证退款金额不能超过订单金额
            order_amount_cents = _to_cents(order.amount, order.currency)
            if payload.refund_amount > order_amount_cents:
                raise BadRequestException(
                    error=RefundError.REFUND_AMOUNT_EXCEEDS_PAYMENT,
                    message=f"退款金额 ({payload.refund_amount}) 不能超过订单金额 ({order_amount_cents})",
                    data={
                        "refund_amount": payload.refund_amount,
                        "order_amount": order_amount_cents,
                        "currency": order.currency,
                    },
                )
            refund_amount_cents = payload.refund_amount

        refund_result = await payment_client.create_refund(
            payment_id=order.payment_id,
            refund_amount=refund_amount_cents,
            reason=payload.reason,
        )

        # 更新订单状态
        order.status = OrderStatus.refunded
        await db.commit()
        await db.refresh(order)

        logger.info(
            f"创建退款成功: order_id={order.order_no}, refund_id={refund_result.id}"
        )

        return RefundOut(
            refund_id=str(refund_result.id),
            order_id=order.order_no,
            payment_id=str(refund_result.payment_id),
            refund_amount=refund_result.refund_amount,
            reason=refund_result.reason,
            status=refund_result.status,
            provider=refund_result.provider,
            provider_refund_id=refund_result.provider_refund_id,
            created_at=refund_result.created_at,
            updated_at=refund_result.updated_at,
            refunded_at=refund_result.refunded_at,
        )

    except PaymentGatewayError as e:
        logger.error(f"支付网关创建退款失败: {e.code} - {e.message}")
        raise BadRequestException(
            error=RefundError.CREATE_REFUND_FAILED,
            message=f"创建退款失败: {e.message}",
        )

    except Exception as e:
        logger.error(f"创建退款失败: {e}")
        raise BadRequestException(
            error=RefundError.CREATE_REFUND_FAILED,
            message=f"创建退款失败: {e}",
        )


async def handle_payment_callback(
    db: AsyncSession,
    order_id: str,
    payment_id: str,
    status: str,
    paid_amount: float | None = None,
    paid_at: datetime | None = None,
    error_message: str | None = None,
) -> Order:
    """
    处理支付网关回调

    Args:
        db: 数据库会话
        order_id: 业务订单号
        payment_id: 支付网关支付ID
        status: 支付状态
        paid_amount: 实际支付金额
        paid_at: 支付时间
        error_message: 错误信息

    Returns:
        更新后的订单
    """
    # 查找订单
    result = await db.execute(select(Order).where(Order.order_no == order_id))
    order = result.scalar_one_or_none()

    if not order:
        logger.warning(f"回调订单不存在: order_id={order_id}")
        raise NotFoundException(OrderError.ORDER_NOT_FOUND)

    # 幂等性检查：如果订单已经处理过，直接返回
    if order.status in [OrderStatus.fulfilled, OrderStatus.refunded]:
        logger.info(f"订单已处理过: order_id={order_id}, status={order.status.value}")
        return order

    # 根据支付状态更新订单
    if status in ["succeeded", "completed"]:
        order.status = OrderStatus.paid
        order.paid_at = paid_at or tz_now()

        # 执行业务处理
        await _fulfill_order(db, order)

    elif status == "failed":
        order.status = OrderStatus.cancelled
        order.extra_metadata = order.extra_metadata or {}
        order.extra_metadata["error_message"] = error_message or "支付失败"

    elif status in ["cancelled", "canceled"]:
        order.status = OrderStatus.cancelled
        order.extra_metadata = order.extra_metadata or {}
        order.extra_metadata["error_message"] = error_message or "支付已取消"

    elif status == "expired":
        order.status = OrderStatus.expired
        order.extra_metadata = order.extra_metadata or {}
        order.extra_metadata["error_message"] = error_message or "订单已过期"

    else:
        logger.warning(f"未知的支付状态: status={status}")

    await db.commit()
    await db.refresh(order)

    logger.info(
        f"处理支付回调: order_id={order_id}, payment_id={payment_id}, "
        f"status={status} -> order_status={order.status.value}"
    )

    return order


async def _fulfill_order(db: AsyncSession, order: Order) -> None:
    """
    执行订单业务处理

    Args:
        db: 数据库会话
        order: 订单对象
    """
    if order.order_type == OrderType.credit_recharge:
        # 积分充值
        await _fulfill_credit_recharge(db, order)
    elif order.order_type == OrderType.subscription:
        # 订阅购买
        await _fulfill_subscription(db, order)

    order.status = OrderStatus.fulfilled


async def _fulfill_credit_recharge(db: AsyncSession, order: Order) -> None:
    """
    处理积分充值

    Args:
        db: 数据库会话
        order: 订单对象
    """


async def _fulfill_subscription(db: AsyncSession, order: Order) -> None:
    """
    处理订阅购买

    Args:
        db: 数据库会话
        order: 订单对象
    """
    # 月数：直接使用订单 quantity
    months = order.quantity or 0
    if months <= 0:
        logger.error(f"订阅订单缺少订阅月数: order_id={order.order_no}")
        return

    # 订阅计划
    plan_config = await query_plan_config(
        db, str(order.subscription_plan_config.plan_code)
    )
    if not plan_config:
        logger.error(f"订阅订单缺少订阅计划: order_id={order.order_no}")
        return

    # 获取用户
    result = await db.execute(select(User).where(User.id == order.user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"用户不存在: user_id={order.user_id}")
        return

    # 更新订阅计划（使用外键ID）
    user.subscription_plan_id = plan_config.id

    # 计算订阅到期时间
    now = tz_now()
    if user.subscription_ends_at and user.subscription_ends_at > now:
        # 如果当前订阅未过期，在原有基础上延长
        new_end_time = user.subscription_ends_at + timedelta(days=30 * months)
    else:
        # 如果当前订阅已过期或没有订阅，从现在开始计算
        new_end_time = now + timedelta(days=30 * months)

    user.subscription_ends_at = new_end_time

    logger.info(
        f"订阅升级成功: user_id={order.user_id}, plan={plan_config.plan_code}, "
        f"months={months}, ends_at={new_end_time}"
    )
