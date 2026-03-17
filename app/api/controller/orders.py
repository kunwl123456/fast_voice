"""
订单控制器

处理订单相关的业务逻辑，作为前端与支付网关之间的桥梁
"""

from __future__ import annotations

import traceback
from datetime import timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    TxType,
    Currency,
    OrderType,
    OrderStatus,
    PaymentProvider,
    ORDER_EXPIRE_MINUTES,
    SUBSCRIPTION_DAYS_PER_MONTH,
)
from app.core.models import (
    User,
    Order,
    CreditPackage,
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
from app.api.services.plan_config import get_plan_config_by_id
from app.core.exceptions import BadRequestException, NotFoundException
from app.api.services.billing import (
    recharge as recharge_credits,
    revoke_credits,
)
from app.api.services.payment_gateway_client import (
    get_payment_gateway_client,
    PaymentGatewayError,
    PaymentStatus,
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
        if settings.payment_callback_url:
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
            select(Order)
            .where(Order.order_no == order_no, Order.user_id == user.id)
            .options(selectinload(Order.subscription_plan_config))
        )
    else:
        result = await db.execute(
            select(Order)
            .where(Order.order_no == order_no)
            .options(selectinload(Order.subscription_plan_config))
        )

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
    page: int = 1,
    page_size: int = 50,
) -> list[OrderListOut]:
    """
    获取订单列表

    Args:
        db: 数据库会话
        user: 当前用户
        page: 页码，从1开始
        page_size: 每页数量

    Returns:
        订单列表
    """
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(page_size)
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

    if not order.payment_id:
        raise BadRequestException(
            error=OrderError.CANNOT_CANCEL_ORDER,
            message="订单缺少支付记录，无法取消",
            data={"order_id": order.order_no},
        )

    try:
        payment_client = get_payment_gateway_client()
        cancel_success = await payment_client.cancel_payment(
            merchant_order_no=order.order_no,
            payment_id=order.payment_id,
        )
        if not cancel_success:
            raise BadRequestException(
                error=OrderError.CANNOT_CANCEL_ORDER,
                message="支付网关取消失败",
                data={"order_id": order.order_no, "payment_id": order.payment_id},
            )
    except PaymentGatewayError as e:
        logger.error(f"支付网关取消订单失败: {e.code} - {e.message}")
        raise BadRequestException(
            error=OrderError.CANNOT_CANCEL_ORDER,
            message=f"取消订单失败: {e.message}",
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

    if order.status == OrderStatus.refunded:
        raise BadRequestException(
            error=RefundError.ORDER_ALREADY_REFUNDED,
            message="订单已退款，无法重复退款",
            data={"order_id": order.order_no},
        )

    if order.status == OrderStatus.refunding:
        raise BadRequestException(
            error=RefundError.REFUND_ALREADY_PROCESSED,
            message="退款处理中，请等待回调确认结果",
            data={"order_id": order.order_no},
        )

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
        if payload.refund_amount is not None:
            # 验证退款金额不能超过订单金额
            if payload.refund_amount > order.amount:
                raise BadRequestException(
                    error=RefundError.REFUND_AMOUNT_EXCEEDS_PAYMENT,
                    message=f"退款金额 ({payload.refund_amount}) 不能超过订单金额 ({order.amount})",
                    data={
                        "refund_amount": payload.refund_amount,
                        "order_amount": order.amount,
                        "currency": order.currency,
                    },
                )

        refund_result = await payment_client.create_refund(
            payment_id=order.payment_id,
            refund_amount=payload.refund_amount,
            reason=payload.reason,
            notify_url=settings.refund_callback_url,
        )

        # 仅记录退款申请信息，订单状态由回调确认
        em = order.extra_metadata or {}
        em["pre_refund_status"] = order.status.value
        em["refund_id"] = str(refund_result.id)
        em["refund_provider_refund_id"] = refund_result.provider_refund_id
        em["refund_requested_at"] = tz_now().isoformat()
        order.extra_metadata = em
        order.status = OrderStatus.refunding
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


async def handle_payment_callback(db: AsyncSession, payload: dict) -> bool:
    """
    处理支付网关「支付回调」事件（按 order_type 分发：订阅 / 购买积分）
    """
    status = payload.get("status")
    payment_id = payload.get("payment_id")
    order_no = payload.get("merchant_order_no")
    if not all([status, payment_id, order_no]):
        logger.error(f"支付回调缺少必要字段: {payload=}")
        return False

    # 查找订单（加锁保证并发安全）
    result = await db.execute(
        select(Order).where(Order.order_no == order_no).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        logger.error(f"回调订单不存在: order_no={order_no} {payload=}")
        return False

    # 安全校验：如果订单已经记录过 payment_id，则必须与回调保持一致
    # （防止伪造回调把别人的订单号 + 自己的 payment_id 混在一起）
    if order.payment_id and str(order.payment_id) != str(payment_id):
        logger.error(
            "支付回调 payment_id 不匹配: "
            f"order_no={order_no}, order.payment_id={order.payment_id}, callback.payment_id={payment_id}"
        )
        return False

    # 幂等：已完成/已退款不重复处理
    if order.status in [OrderStatus.fulfilled, OrderStatus.refunded]:
        logger.info(f"订单已处理过: order_no={order_no}, status={order.status.value}")
        return True

    # 退款处理中，忽略支付回调，避免状态被覆盖
    if order.status == OrderStatus.refunding:
        logger.info(f"订单退款中，忽略支付回调: order_no={order_no}")
        return True

    # 防重复履约：历史版本可能存在“paid 已落库但未履约/未标记 fulfilled”的中间态。
    # 这里优先保证不会重复加积分/重复延长订阅；需要补偿的 paid 订单可通过后台对账/脚本处理。
    if order.status == OrderStatus.paid:
        logger.info(f"订单已是 paid，跳过重复履约: order_no={order_no}")
        return True

    status_norm = str(status).lower()
    match status_norm:

        # - pending: 保持待支付（仅记录网关状态），不履约
        case PaymentStatus.pending.value:
            order.status = OrderStatus.pending
            em = order.extra_metadata or {}
            em["gateway_status"] = status_norm
            em["gateway_payment_id"] = payment_id
            order.extra_metadata = em
            db.add(order)
            await db.flush()
            return True

        case "failed":
            # - failed: 标记失败
            order.status = OrderStatus.failed
            em = order.extra_metadata or {}
            em["gateway_status"] = status_norm
            em["gateway_payment_id"] = payment_id
            em["error_message"] = (
                payload.get("error_message")
                or payload.get("message")
                or em.get("error_message", "")
            )
            order.extra_metadata = em
            db.add(order)
            await db.flush()
            return True

        case "canceled":
            # - canceled: 标记已取消
            order.status = OrderStatus.cancelled
            em = order.extra_metadata or {}
            em["gateway_status"] = status_norm
            em["gateway_payment_id"] = payment_id
            order.extra_metadata = em
            db.add(order)
            await db.flush()
            return True

        # - succeeded: 支付成功，标记 paid 并履约
        case PaymentStatus.succeeded.value:
            order.status = OrderStatus.paid
            order.paid_at = tz_now()
            em = order.extra_metadata or {}
            em["gateway_status"] = status_norm
            em["gateway_payment_id"] = payment_id
            order.extra_metadata = em

            try:
                is_fulfilled, msg = await _fulfill_order(db, order)
                if is_fulfilled:
                    order.status = OrderStatus.fulfilled
                else:
                    # 履约失败，但支付已成功。
                    # 保持为 paid，记录错误信息，后续需监控报警并人工/脚本补单
                    order.status = OrderStatus.paid
                    em = order.extra_metadata or {}
                    em["fulfill_error"] = msg or "订单履约失败"
                    order.extra_metadata = em
                    logger.error(
                        f"订单支付成功但履约失败: order_no={order.order_no}, error={msg}"
                    )

            except Exception as e:
                # 履约异常：记录错误并保持 paid，让支付中台按策略重试/人工排查
                logger.error(f"订单履约异常：{traceback.format_exc()}")
                order.status = OrderStatus.paid
                em = order.extra_metadata or {}
                em["fulfill_error"] = f"订单履约异常: {str(e)}"
                order.extra_metadata = em

            db.add(order)
            await db.flush()
            logger.info(
                f"处理支付回调成功: order_no={order.order_no}, type={order.order_type.value}, "
                f"gateway_payment_id={payment_id}, status={status_norm}"
            )
            return True

        case _:
            # 未知状态：不确认，交由网关重试/人工排查
            logger.warning(
                f"未知支付状态: order_no={order_no}, status={status_norm} {payload=}"
            )
            return False


async def handle_refund_callback(db: AsyncSession, payload: dict) -> bool:
    """
    处理支付网关「退款回调」事件（按 order_type 分发：订阅 / 购买积分）

    当前版本仅同步订单状态为 refunded（不做业务侧回滚）。
    """
    status = payload.get("status")
    payment_id = payload.get("payment_id")
    order_no = payload.get("merchant_order_no")
    if not order_no or not status:
        logger.error(f"退款回调缺少必要字段: {payload=}")
        return False

    result = await db.execute(
        select(Order).where(Order.order_no == order_no).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        logger.error(f"退款回调订单不存在: order_no={order_no} {payload=}")
        return False

    # 安全校验：若已记录 payment_id，则必须与回调一致
    if payment_id and order.payment_id and str(order.payment_id) != str(payment_id):
        logger.error(
            "退款回调 payment_id 不匹配: "
            f"order_no={order_no}, order.payment_id={order.payment_id}, callback.payment_id={payment_id}"
        )
        return False

    # 幂等：已退款直接返回
    if order.status == OrderStatus.refunded:
        logger.info(f"订单已退款(幂等): order_no={order_no}")
        return True

    status_norm = str(status).lower()
    if status_norm in ["refunded", "succeeded", "completed"]:
        # 仅当从非 refunded 状态变为 refunded 时执行回滚
        if order.status != OrderStatus.refunded:
            order.status = OrderStatus.refunded

            # 执行业务侧权益回滚
            try:
                await _rollback_order_benefits(db, order)
                logger.info(f"订单权益回滚成功: order_no={order.order_no}")
            except Exception as e:
                # 回滚失败记录错误，但不阻止状态更新（权益未回收是损失，但不能阻塞流程）
                logger.error(f"订单权益回滚失败: order_no={order.order_no}, error={e}")
                em = order.extra_metadata or {}
                em["rollback_error"] = str(e)
                order.extra_metadata = em

    elif status_norm in ["failed", "canceled", "cancelled"]:
        # 退款失败：恢复为退款前状态（默认回退到 paid）
        em = order.extra_metadata or {}
        prev_status = em.get("pre_refund_status") or OrderStatus.fulfilled.value
        try:
            order.status = OrderStatus(prev_status)
        except Exception:
            order.status = OrderStatus.paid
    else:
        # 未知退款状态：不确认成功
        logger.warning(
            f"未知退款状态: order_no={order_no}, status={status_norm} {payload=}"
        )
        return False

    em = order.extra_metadata or {}
    em["refund_gateway_status"] = status_norm
    em["refund_gateway_payment_id"] = payment_id
    em["refund_id"] = (
        payload.get("refund_id") or payload.get("id") or em.get("refund_id")
    )
    order.extra_metadata = em

    db.add(order)
    await db.flush()
    logger.info(
        f"处理退款回调成功: order_no={order.order_no}, type={order.order_type.value}, status={status_norm}"
    )
    return True


async def _fulfill_order(db: AsyncSession, order: Order) -> (bool, str):
    """
    执行订单业务处理

    Args:
        db: 数据库会话
        order: 订单对象
    """
    if order.order_type == OrderType.credit_recharge:
        # 积分充值
        return await _fulfill_credit_recharge(db, order)
    elif order.order_type == OrderType.subscription:
        # 订阅购买
        return await _fulfill_subscription(db, order)

    return False, "不匹配的订单类型"


async def _fulfill_credit_recharge(db: AsyncSession, order: Order) -> (bool, str):
    """
    处理积分充值

    Args:
        db: 数据库会话
        order: 订单对象
    """
    pkg = None
    if order.product_id:
        pkg = (
            await db.execute(
                select(CreditPackage).where(CreditPackage.id == order.product_id)
            )
        ).scalar_one_or_none()
        if not pkg:
            logger.error(
                f"积分充值订单档位不存在: order_id={order.order_no}, product_id={order.product_id}"
            )
            return False, "积分充值订单档位不存在"

    # 回退兼容历史订单：使用 extra_metadata 里的档位编码
    if not pkg:
        em = order.extra_metadata or {}
        package_code = em.get("credit_package_code") or em.get("package_code")
        if not package_code:
            logger.error(f"积分充值订单缺少档位信息: order_id={order.order_no}")
            return False, "积分充值订单缺少档位信息"

        # 查档位（不限制 is_active：历史订单仍需可履约）
        pkg = (
            await db.execute(
                select(CreditPackage).where(CreditPackage.code == package_code)
            )
        ).scalar_one_or_none()
        if not pkg:
            logger.error(
                f"积分充值订单档位不存在: order_id={order.order_no}, package_code={package_code}"
            )
            return False, f"积分充值订单档位不存在：{package_code=}"

    quantity = int(order.quantity or 1)
    credits_to_add = int(pkg.credits) * quantity

    # 入账（带行锁，原子增加余额并写流水）
    await recharge_credits(
        db=db,
        user_id=order.user_id,
        amount=credits_to_add,
        note=f"购买积分：{pkg.name} x{quantity}",
        ref_id=order.order_no,
        ref_type="recharge",
        tx_type=TxType.recharge,
        commit=False,
    )
    logger.info(
        f"积分充值履约完成: order_id={order.order_no}, "
        f"package={pkg.code}, credits={credits_to_add}"
    )
    return True, ""


async def _fulfill_subscription(db: AsyncSession, order: Order) -> (bool, str):
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
        return False, "订阅订单缺少订阅月数"

    # 订阅计划（使用订单上的 product_id，避免依赖 relationship 的懒加载）
    if not order.product_id:
        logger.error(f"订阅订单缺少订阅计划ID(product_id): order_id={order.order_no}")
        return False, "订阅订单缺少订阅计划ID"

    plan_config = await get_plan_config_by_id(db, int(order.product_id))
    if not plan_config:
        logger.error(f"订阅订单缺少订阅计划: order_id={order.order_no}")
        return False, "订阅订单缺少订阅计划"

    # 获取用户
    result = await db.execute(select(User).where(User.id == order.user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"用户不存在: user_id={order.user_id}")
        return False, "用户不存在"

    # 计算订阅到期时间
    now = tz_now()
    if user.subscription_ends_at and user.subscription_ends_at > now:
        # 如果当前订阅未过期，在原有基础上延长
        new_end_time = user.subscription_ends_at + timedelta(
            days=SUBSCRIPTION_DAYS_PER_MONTH * months
        )
    else:
        # 如果当前订阅已过期或没有订阅，从现在开始计算
        new_end_time = now + timedelta(days=SUBSCRIPTION_DAYS_PER_MONTH * months)

    # 更新订阅计划
    user.subscription_plan_id = plan_config.id
    user.subscription_ends_at = new_end_time
    db.add(user)

    # 订阅赠送积分：只赠送第1个月积分（后续由定时任务按月续赠）
    credits_added = int(getattr(plan_config, "monthly_credits", 0) or 0)
    if credits_added > 0:
        # 入账（带行锁，原子增加余额并写流水）
        await recharge_credits(
            db=db,
            user_id=order.user_id,
            amount=credits_added,
            note=f"订阅{plan_config.name}赠送积分（第1个月）",
            ref_id=order.order_no,
            ref_type="subscription",
            tx_type=TxType.subscription,
            commit=False,
        )

    logger.info(
        f"订阅升级成功: user_id={order.user_id}, plan={plan_config.plan_code}, "
        f"months={months}, ends_at={new_end_time}, credits_added={credits_added}"
    )
    return True, ""


async def _rollback_order_benefits(db: AsyncSession, order: Order) -> None:
    """
    回滚订单权益（退款时调用）
    """
    if order.order_type == OrderType.credit_recharge:
        # 1. 积分充值回滚
        pkg = None
        if order.product_id:
            pkg = (
                await db.execute(
                    select(CreditPackage).where(CreditPackage.id == order.product_id)
                )
            ).scalar_one_or_none()

        # 如果找不到 ID，尝试 code
        if not pkg:
            em = order.extra_metadata or {}
            package_code = em.get("credit_package_code") or em.get("package_code")
            if package_code:
                pkg = (
                    await db.execute(
                        select(CreditPackage).where(CreditPackage.code == package_code)
                    )
                ).scalar_one_or_none()

        credits_to_deduct = 0
        if pkg:
            quantity = int(order.quantity or 1)
            credits_to_deduct = int(pkg.credits) * quantity
        else:
            logger.warning(
                f"回滚积分失败：找不到对应套餐信息 order_no={order.order_no}"
            )
            return

        if credits_to_deduct > 0:
            await revoke_credits(
                db=db,
                user_id=order.user_id,
                amount=credits_to_deduct,
                ref_type="refund_rollback",
                ref_id=order.order_no,
                note=f"订单退款，回收积分: {order.order_no}",
            )

    elif order.order_type == OrderType.subscription:
        # 2. 订阅回滚
        # A. 回收积分（如果有赠送）
        plan_config = (
            await get_plan_config_by_id(db, int(order.product_id))
            if order.product_id
            else None
        )

        if plan_config:
            credits_added = int(getattr(plan_config, "monthly_credits", 0) or 0)
            if credits_added > 0:
                await revoke_credits(
                    db=db,
                    user_id=order.user_id,
                    amount=credits_added,
                    ref_type="refund_rollback",
                    ref_id=order.order_no,
                    note=f"订阅退款，回收赠送积分: {order.order_no}",
                )

        # B. 回退订阅时间
        result = await db.execute(
            select(User).where(User.id == order.user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if user and user.subscription_ends_at:
            months = order.quantity or 0
            if months > 0:
                # 回退天数
                days_to_reduce = SUBSCRIPTION_DAYS_PER_MONTH * months
                user.subscription_ends_at = user.subscription_ends_at - timedelta(
                    days=days_to_reduce
                )
                db.add(user)
